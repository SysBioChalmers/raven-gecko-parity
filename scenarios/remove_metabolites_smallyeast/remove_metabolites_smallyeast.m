function results = remove_metabolites_smallyeast(ctx)
% MATLAB side of the metabolite-removal scenario.
%
% removeMets, called with every removeUnused* flag at its shared default of
% false, deletes exactly the named metabolites and nothing else: a reaction
% that used one keeps its other metabolites and loses that row from S, and a
% reaction whose only metabolite was removed is left in the model with zero
% metabolites rather than being pruned.

inputs = ctx.inputs;

results.by_id = by_id_checkpoint(inputs);
results.by_name = by_name_checkpoint(inputs);

end


function out = by_id_checkpoint(inputs)
model = readYAMLmodel(inputs.model);
beforeMets = model.mets(:);

touched = {'glyOUT', 'GPP', 'HXK', 'PFK', 'PGK', 'PYK', ...
    'ACS', 'PYC', 'LSC1LSC2', 'PCK', 'GROWTH', 'NADHX', 'FADHX', 'ATPX'};
beforeSizes = containers.Map('KeyType', 'char', 'ValueType', 'double');
for k = 1:numel(touched)
    i = find(strcmp(model.rxns, touched{k}), 1);
    beforeSizes(touched{k}) = nnz(model.S(:, i));
end

reduced = removeMets(model, as_cellstr(inputs.removed_by_id), ...
    'isNames', false, ...
    'removeUnusedRxns', false, 'removeUnusedGenes', false, 'removeUnusedComps', false);

afterMets = reduced.mets(:);

out.n_reactions = numel(reduced.rxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);
out.removed_metabolites = sort_cellstr(setdiff(beforeMets, afterMets));

records = cell(1, numel(touched));
for k = 1:numel(touched)
    i = find(strcmp(reduced.rxns, touched{k}), 1);
    records{k} = struct( ...
        'reaction', touched{k}, ...
        'n_metabolites_before', beforeSizes(touched{k}), ...
        'n_metabolites_after', nnz(reduced.S(:, i)), ...
        'stoichiometry', {reaction_stoichiometry(reduced, i)});
end
out.reactions = records;
end


function out = by_name_checkpoint(inputs)
model = readYAMLmodel(inputs.model);
beforeMets = model.mets(:);

reduced = removeMets(model, {char(inputs.removed_by_name)}, ...
    'isNames', true, ...
    'removeUnusedRxns', false, 'removeUnusedGenes', false, 'removeUnusedComps', false);

afterMets = reduced.mets(:);

out.n_reactions = numel(reduced.rxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);
out.removed_metabolites = sort_cellstr(setdiff(beforeMets, afterMets));
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


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end


function out = as_cellstr(value)
if ischar(value)
    out = {value};
elseif iscell(value)
    out = value(:)';
    for k = 1:numel(out)
        if isstring(out{k})
            out{k} = char(out{k});
        end
    end
else
    out = {};
end
end
