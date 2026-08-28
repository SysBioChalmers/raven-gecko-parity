function results = ec_model_io_ectestgem(ctx)
% MATLAB side of the ecModel save/load scenario.
%
% Same three checkpoints as run.py, and the same conventions carried over from
% ec_model_expansion_ectestgem for the same reasons: an infinite bound is a class and a
% zero; ec.rxns / ec.genes / ec.enzymes are left in their own order, since the expansion
% order is the result; stoichiometry, gene associations and the coupling matrix are sorted
% multi-key records, joined on char(1) so the sort matches Python's tuple comparison.
% ec.concs is left out of the summary --- see run.py for why (NaN cannot survive an
% isequal-based round-trip check).
%
% Line endings are normalised to \n before the written file is emitted, as in
% yaml_roundtrip_smallyeast.m: fopen in text mode writes CRLF on Windows, which is a
% property of this harness, not of saveEcModel.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);
ecModel = makeEcModel(model, false, adapter);

results.direct = summary(ecModel);

workdir = tempname;
mkdir(fullfile(workdir, 'models'));
cleanup = onCleanup(@() rmdir(workdir, 's'));

% saveEcModel always joins its filename onto <adapter path>/models/, even given an
% absolute path --- unlike save_ec_model, which honours an absolute path as-is. A
% throwaway copy of the adapter with its path pointed at a temp directory is what routes
% the write there instead of into the fixture's own models/ folder. ModelAdapter is a
% value class, so this copy cannot affect the adapter used anywhere else.
ioAdapter = adapter;
ioAdapter.params.path = workdir;

saveEcModel(ecModel, 'ecModel.yml', ioAdapter);
outputFile = fullfile(workdir, 'models', 'ecModel.yml');

results.written = file_record(outputFile);

reread = loadEcModel('ecModel.yml', ioAdapter);

results.roundtrip = summary(reread);
results.roundtrip.identical_to_direct = isequal(results.roundtrip, results.direct);

end


function record = file_record(path)
text = fileread(path);
text = strrep(text, sprintf('\r\n'), sprintf('\n'));
lines = strsplit(text, sprintf('\n'), 'CollapseDelimiters', false);
if ~isempty(lines) && isempty(lines{end})
    lines(end) = [];
end

record.n_lines = numel(lines);
record.n_chars = sum(cellfun(@numel, lines));
record.lines = reshape(lines, 1, []);
end


function out = summary(model)
out.model_id = model.id;
out.n_reactions = numel(model.rxns);
out.n_metabolites = numel(model.mets);
out.n_genes = numel(model.genes);

[rxnIds, rxnOrder] = sort(model.rxns(:));
reactions = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    i = rxnOrder(k);
    [lowerValue, lowerKind] = bound(model.lb(i));
    [upperValue, upperKind] = bound(model.ub(i));
    reactions{k} = struct( ...
        'id',                     rxnIds{k}, ...
        'lower_bound',            lowerValue, ...
        'lower_kind',             lowerKind, ...
        'upper_bound',            upperValue, ...
        'upper_kind',             upperKind, ...
        'objective_coefficient',  double(model.c(i)));
end
out.reactions = reactions;

[metIds, metOrder] = sort(model.mets(:));
metabolites = cell(1, numel(metIds));
for k = 1:numel(metIds)
    i = metOrder(k);
    metabolites{k} = struct( ...
        'id',          metIds{k}, ...
        'name',        model.metNames{i}, ...
        'compartment', model.comps{model.metComps(i)});
end
out.metabolites = metabolites;

out.genes = reshape(sort(model.genes(:)), 1, []);
out.gene_associations = pairs(model.rxnGeneMat, model.rxns, model.genes, ...
    {'reaction', 'gene'}, false);
out.stoichiometry = pairs(model.S.', model.rxns, model.mets, ...
    {'reaction', 'metabolite'}, true);

out.gecko_light = logical(model.ec.geckoLight);
out.ec = ec_data(model.ec);
end


function out = ec_data(ec)
out.rxns     = reshape(ec.rxns(:), 1, []);
out.genes    = reshape(ec.genes(:), 1, []);
out.enzymes  = reshape(ec.enzymes(:), 1, []);
out.mw       = reshape(double(ec.mw(:)), 1, []);
out.sequence = reshape(ec.sequence(:), 1, []);
out.eccodes  = reshape(blanks_for_empty(ec.eccodes), 1, []);
out.kcat     = reshape(double(ec.kcat(:)), 1, []);
out.coupling = pairs(ec.rxnEnzMat, ec.rxns, ec.enzymes, {'reaction', 'enzyme'}, true);
end


function [value, kind] = bound(x)
if isinf(x) && x > 0
    value = 0;
    kind = '+inf';
elseif isinf(x) && x < 0
    value = 0;
    kind = '-inf';
else
    value = double(x);
    kind = 'finite';
end
end


function out = pairs(matrix, rowIds, colIds, names, withCoefficient)
[rows, cols, values] = find(matrix);
keys = cell(numel(rows), 1);
for k = 1:numel(rows)
    keys{k} = [rowIds{rows(k)} char(1) colIds{cols(k)}];
end
[~, order] = sort(keys);

out = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    record = struct(names{1}, rowIds{rows(i)}, names{2}, colIds{cols(i)});
    if withCoefficient
        record.coefficient = double(values(i));
    end
    out{k} = record;
end
end


function out = blanks_for_empty(values)
out = values(:).';
for k = 1:numel(out)
    if isempty(out{k})
        out{k} = '';
    end
end
end
