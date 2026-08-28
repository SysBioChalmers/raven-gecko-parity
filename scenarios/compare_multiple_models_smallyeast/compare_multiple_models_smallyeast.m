function results = compare_multiple_models_smallyeast(ctx)
% MATLAB side of the multi-model comparison scenario.
%
% compareMultipleModels builds compStruct.reactions.IDs / .matrix via a
% generic "unique entries x frequency per model" helper; for model.rxns a
% reaction id cannot repeat within one model, so the frequency is exactly 0
% or 1 --- the same presence matrix compare_models builds directly. Only this
% one field is used here; see scenario.yml for why metabolites, genes,
% subsystems, similarity and tasks are not.

inputs = ctx.inputs;
path = inputs.model;

full = readYAMLmodel(path);
full.id = 'full';

minusTwo = readYAMLmodel(path);
minusTwo.id = 'minus_two';
minusTwo = removeReactions(minusTwo, as_cellstr(inputs.minus_two_removed));

minusOnePlusOne = readYAMLmodel(path);
minusOnePlusOne.id = 'minus_one_plus_one';
minusOnePlusOne = removeReactions(minusOnePlusOne, {char(inputs.minus_one_plus_one_removed)});
added = inputs.minus_one_plus_one_added;
rxnsToAdd.rxns = {char(added.id)};
rxnsToAdd.equations = {char(added.equation)};
rxnsToAdd.rxnNames = {char(added.name)};
minusOnePlusOne = addRxns(minusOnePlusOne, rxnsToAdd, ...
    'eqnType', 1, 'allowNewMets', false, 'allowNewGenes', false);

models = {full, minusTwo, minusOnePlusOne};
compStruct = compareMultipleModels(models, 'printResults', false);

modelIds = compStruct.modelIDs;
ids = compStruct.reactions.IDs;
matrix = compStruct.reactions.matrix;

results.model_ids = row(modelIds);

perModel = struct();
for k = 1:numel(modelIds)
    perModel.(modelIds{k}) = sum(matrix(:, k));
end
results.n_reactions_per_model = perModel;
results.n_reactions_total = numel(ids);

[sortedIds, order] = sort(ids);
records = cell(1, numel(sortedIds));
for k = 1:numel(sortedIds)
    i = order(k);
    record = struct('reaction', sortedIds{k});
    for m = 1:numel(modelIds)
        record.(modelIds{m}) = double(matrix(i, m) ~= 0);
    end
    records{k} = record;
end
results.reactions = records;

end


function out = row(values)
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
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
