function results = enzyme_annotation_ectestgem(ctx)
% MATLAB side of the enzyme-annotation scenario.
%
% Must return exactly the shape run.py returns. Two conventions carried over from
% ec_model_expansion_ectestgem, for the same reasons:
%   * ec.rxns order is the result, so eccodes lists are emitted in that order, unsorted;
%   * ec.rxnEnzMat is emitted as (reaction, enzyme, coefficient) records sorted on the two
%     keys joined with char(1), which is what reproduces Python's tuple ordering.
%
% Where the two APIs differ, the difference is handled rather than measured: MATLAB
% selects a subset of ec reactions with a logical mask over ec.rxns, geckopy with a list of
% names, and both are built from the same declared list in the scenario.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

results.full  = annotate(model, false, cellstr(ctx.inputs.subset_full),  adapter);
results.light = annotate(model, true,  cellstr(ctx.inputs.subset_light), adapter);

end


function out = annotate(model, geckoLight, subset, adapter)
ecModel = makeEcModel(model, geckoLight, adapter);
out.ec_rxns = reshape(ecModel.ec.rxns(:), 1, []);

% Each function is handed the same freshly expanded ecModel and its result is read from
% the copy it returns, so no checkpoint depends on the order the others ran in. That is
% free in MATLAB, where a model is a value; the Python side has to rebuild the model.
complexes = applyComplexData(ecModel, [], adapter, false);
out.complexes = pairs(complexes.ec.rxnEnzMat, complexes.ec.rxns, complexes.ec.enzymes);

selected = ismember(ecModel.ec.rxns, subset);
out.eccodes_from_gem             = eccodes(getECfromGEM(ecModel));
out.eccodes_from_gem_subset      = eccodes(getECfromGEM(ecModel, selected));
out.eccodes_from_database        = eccodes(getECfromDatabase(ecModel, [], 'display', adapter));
out.eccodes_from_database_subset = eccodes(getECfromDatabase(ecModel, selected, 'display', adapter));
end


function out = eccodes(model)
% An unassigned EC code is [] in MATLAB and '' in Python; both are emitted as the empty
% string, so that "no code here" is a value both sides can state rather than a structural
% difference.
out = model.ec.eccodes(:).';
for k = 1:numel(out)
    if isempty(out{k})
        out{k} = '';
    end
end
end


function out = pairs(matrix, rowIds, colIds)
% Non-zero entries of ec.rxnEnzMat as a sorted list of records.
%
% A cell array of structs rather than a struct array: jsonencode turns a 1x1 struct array
% into a bare object instead of a one-element array. Sorted on the keys joined with
% char(1), which is below every character an identifier can contain --- joining with a
% printable separator does not reproduce Python's tuple comparison.
[rows, cols, values] = find(matrix);
keys = cell(numel(rows), 1);
for k = 1:numel(rows)
    keys{k} = [rowIds{rows(k)} char(1) colIds{cols(k)}];
end
[~, order] = sort(keys);

out = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    out{k} = struct( ...
        'reaction',    rowIds{rows(i)}, ...
        'enzyme',      colIds{cols(i)}, ...
        'coefficient', double(values(i)));
end
end
