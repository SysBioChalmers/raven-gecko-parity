function results = ec_model_expansion_ectestgem(ctx)
% MATLAB side of the ecModel-expansion scenario.
%
% Must return exactly the shape run.py returns --- same field names, same ordering rules,
% same conventions --- because `parity compare` diffs the two structurally.
%
% Four conventions, each of which is the easy way to get a false difference:
%   * bounds --- an infinite bound is emitted as a finite value plus a class, because
%     jsonencode writes Inf as null and the Python side reads that back as the string
%     "Infinity";
%   * sorting --- reactions, metabolites and record lists are sorted by id, and multi-key
%     lists are sorted on the keys joined with char(1), which reproduces Python's tuple
%     comparison (see docs/scenarios.md);
%   * gene associations --- compared as (reaction, gene) pairs rather than as grRules
%     strings, since RAVEN keeps `G1 and G2 or G3` where cobrapy parenthesises it;
%   * ec.rxns order --- *not* sorted. The expansion order is the result here, and MATLAB's
%     own geckoCoreFunctionTests assert it.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

results.adapter = adapter_params(adapter);
results.conventional = gem(model);
% makeEcModel does not modify its input, so both variants start from the same model.
results.full  = ec_model(makeEcModel(model, false, adapter));
results.light = ec_model(makeEcModel(model, true,  adapter));

end


function out = adapter_params(adapter)
% The adapter's own parameters, so that a drift between GECKO's TestGEMAdapter.m and
% geckopy's model_adapter.toml is reported here rather than silently changing what the
% rest of the scenario compares.
p = adapter.getParameters();
out = struct( ...
    'org_name',              p.org_name, ...
    'sigma',                 double(p.sigma), ...
    'p_tot',                 double(p.Ptot), ...
    'f',                     double(p.f), ...
    'gr_exp',                double(p.gR_exp), ...
    'c_source',              p.c_source, ...
    'bio_rxn',               p.bioRxn, ...
    'enzyme_comp',           p.enzyme_comp, ...
    'kegg_id',               p.kegg.ID, ...
    'kegg_gene_id',          p.kegg.geneID, ...
    'uniprot_type',          p.uniprot.type, ...
    'uniprot_id',            p.uniprot.ID, ...
    'uniprot_gene_id_field', p.uniprot.geneIDfield, ...
    'uniprot_reviewed',      logical(p.uniprot.reviewed), ...
    'complex_taxonomic_id',  double(p.complex.taxonomicID));
end


function out = gem(model)
% Everything both implementations agree a metabolic model is: reactions with bounds,
% metabolites with names and compartments, genes, the association matrix and S.
out.n_reactions   = numel(model.rxns);
out.n_metabolites = numel(model.mets);
out.n_genes       = numel(model.genes);

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
end


function out = ec_model(model)
out = gem(model);
% Logical, not 0/1: `parity compare` refuses to read a boolean as a number, so that a
% flag can never masquerade as a count.
out.gecko_light = logical(model.ec.geckoLight);
out.ec = ec_data(model.ec);
end


function out = ec_data(ec)
% ec.rxns, ec.genes and ec.enzymes are left in their own order on both sides: the
% expansion order *is* the result, and sorting it would compare the harness with itself.
out.rxns     = reshape(ec.rxns(:), 1, []);
out.genes    = reshape(ec.genes(:), 1, []);
out.enzymes  = reshape(ec.enzymes(:), 1, []);
out.mw       = reshape(double(ec.mw(:)), 1, []);
out.sequence = reshape(ec.sequence(:), 1, []);
out.eccodes  = reshape(blanks_for_empty(ec.eccodes), 1, []);

% makeEcModel does not fill these in; their length is what the two sides must agree on at
% this stage. ec.concs is NaN on both sides, and NaN survives JSON on neither, so only its
% length is reported.
out.n_kcat   = numel(ec.kcat);
out.n_source = numel(ec.source);
out.n_notes  = numel(ec.notes);
out.n_concs  = numel(ec.concs);
out.kcat     = reshape(double(ec.kcat(:)), 1, []);

out.coupling = pairs(ec.rxnEnzMat, ec.rxns, ec.enzymes, {'reaction', 'enzyme'}, true);
end


function [value, kind] = bound(x)
% An infinite bound carries no number, so it is emitted as a class and a zero --- the
% has_charge/charge convention from docs/scenarios.md, applied to bounds.
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
% Non-zero entries of a matrix as a sorted list of records.
%
% Cell array of structs, not a struct array: jsonencode turns a 1x1 struct array into a
% bare object rather than a one-element array, which would not match the Python side.
% Sorted on the two keys joined with char(1) --- below every character an identifier can
% contain --- which is what reproduces Python's tuple ordering. Joining with a printable
% separator does not: '|' sorts above '_', so R2_EXP_1 would come out on the wrong side
% of R2.
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
% An unset eccode is [] in MATLAB and '' in Python; both are emitted as the empty string
% so that absence is a value rather than a structural difference.
out = values(:).';
for k = 1:numel(out)
    if isempty(out{k})
        out{k} = '';
    end
end
end
