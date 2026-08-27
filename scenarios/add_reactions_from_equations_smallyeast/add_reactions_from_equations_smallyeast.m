function results = add_reactions_from_equations_smallyeast(ctx)
% MATLAB side of the equation-parsing scenario.
%
% addRxns takes a struct of parallel arrays where the Python side takes a
% sequence of mappings, but the fields line up one for one: rxns/id,
% equations/equation, rxnNames/name, grRules/gene_reaction_rule, (lb, ub)/bounds.
%
% Two calls rather than one, because lb and ub are vectors over the whole batch
% --- see scenario.yml.

inputs = ctx.inputs;

results.from_arrows = checkpoint(inputs, inputs.arrow_reactions, false);
results.explicit_bounds = checkpoint(inputs, inputs.bounded_reactions, true);

end


function out = checkpoint(inputs, declared, bounded)
model = readYAMLmodel(inputs.model);
beforeRxns = model.rxns(:);
beforeMets = model.mets(:);
beforeGenes = genes_of(model);

declared = as_struct_array(declared);

rxnsToAdd = struct();
rxnsToAdd.rxns = arrayfun(@(e) {char(e.id)}, declared);
rxnsToAdd.equations = arrayfun(@(e) {char(e.equation)}, declared);
rxnsToAdd.rxnNames = arrayfun(@(e) {char(e.name)}, declared);
rxnsToAdd.grRules = arrayfun(@(e) {char(e.gene_reaction_rule)}, declared);
if bounded
    rxnsToAdd.lb = arrayfun(@(e) double(e.lower_bound), declared);
    rxnsToAdd.ub = arrayfun(@(e) double(e.upper_bound), declared);
end

model = addRxns(model, rxnsToAdd, ...
    'eqnType', 1, ...
    'compartment', char(inputs.compartment), ...
    'allowNewMets', logical(inputs.allow_new_mets), ...
    'allowNewGenes', logical(inputs.allow_new_genes));

afterRxns = model.rxns(:);
afterMets = model.mets(:);
afterGenes = genes_of(model);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(afterRxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);
out.n_genes_before = numel(beforeGenes);
out.n_genes_after = numel(afterGenes);

added = sort(setdiff(afterRxns, beforeRxns));
addedMets = setdiff(afterMets, beforeMets);

out.added_reactions = row(added);
out.added_metabolites = sort_cellstr(addedMets);
out.added_genes = sort_cellstr(setdiff(afterGenes, beforeGenes));
out.added_detail = added_detail(model, added);
out.added_metabolite_detail = added_metabolite_detail(model, sort(addedMets));
end


function records = added_detail(model, added)
added = added(:)';
records = cell(1, numel(added));
for k = 1:numel(added)
    i = find(strcmp(model.rxns, added{k}), 1);

    if isfield(model, 'grRules')
        clauses = grRuleToDNF(model.grRules{i});
    else
        clauses = {};
    end
    clauses = clauses(:)';
    keys = cell(1, numel(clauses));
    for j = 1:numel(clauses)
        clauses{j} = sort_cellstr(clauses{j});
        keys{j} = join_key(clauses{j});
    end
    if ~isempty(clauses)
        [~, clauseOrder] = sort(keys);
        clauses = clauses(clauseOrder);
    end

    records{k} = struct( ...
        'reaction', added{k}, ...
        'name', model.rxnNames{i}, ...
        'lower_bound', double(model.lb(i)), ...
        'upper_bound', double(model.ub(i)), ...
        'clauses', {clauses}, ...
        'stoichiometry', {reaction_stoichiometry(model, i)});
end
if isempty(records)
    records = {};
end
end


function records = reaction_stoichiometry(model, rxnIdx)
metIdx = find(model.S(:, rxnIdx) ~= 0)';
[~, order] = sort(model.mets(metIdx));
metIdx = metIdx(order);

records = cell(1, numel(metIdx));
for k = 1:numel(metIdx)
    records{k} = struct( ...
        'metabolite', model.mets{metIdx(k)}, ...
        ... % full(): indexing a sparse S yields a sparse scalar, and
        ... % jsonencode refuses one ("Unable to encode sparse objects").
        'coefficient', double(full(model.S(metIdx(k), rxnIdx))));
end
if isempty(records)
    records = {};
end
end


function records = added_metabolite_detail(model, addedMets)
addedMets = addedMets(:)';
records = cell(1, numel(addedMets));
for k = 1:numel(addedMets)
    i = find(strcmp(model.mets, addedMets{k}), 1);
    % The created metabolite's name is deliberately not compared --- see
    % scenario.yml.
    records{k} = struct( ...
        'metabolite', addedMets{k}, ...
        'compartment', model.comps{model.metComps(i)});
end
if isempty(records)
    records = {};
end
end


function out = genes_of(model)
if isfield(model, 'genes')
    out = model.genes(:);
else
    out = {};
end
end


function out = as_struct_array(value)
% jsondecode gives a struct array when every object in the JSON array has the
% same fields, and a cell array of structs when they differ. The scenario keeps
% the keys uniform, but accept both rather than depend on it.
if iscell(value)
    out = [value{:}];
else
    out = value;
end
out = out(:)';
end


function key = join_key(parts)
key = strjoin(parts(:)', char(1));
end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end


function out = row(values)
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
end
