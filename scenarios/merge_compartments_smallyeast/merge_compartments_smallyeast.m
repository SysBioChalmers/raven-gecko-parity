function results = merge_compartments_smallyeast(ctx)
% MATLAB side of the compartment-merging scenario.
%
% mergeCompartments groups by metNames and keeps the id of the first copy it
% finds, so the merged metabolites are compared by name --- see scenario.yml
% for why that is a concession rather than a convenience.
%
% Reactions removed by the merge are reported as the difference between the
% model before and after: RAVEN's deletedRxns covers the deleteRxnsWithOneMet
% mode only, and the reactions that cancelled to nothing are removed separately
% without being reported, so the returned lists are not the same quantity on
% the two sides.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

beforeRxns = model.rxns(:);
beforeSpecies = unique(model.metNames(:));
nMetsBefore = numel(model.mets);

[merged, ~, duplicateRxns] = mergeCompartments(model, ...
    'deleteRxnsWithOneMet', logical(inputs.delete_single_metabolite_reactions), ...
    'distReverse', true);

afterRxns = merged.rxns(:);

results.n_reactions_before = numel(beforeRxns);
results.n_reactions_after = numel(afterRxns);
results.n_species_before = numel(beforeSpecies);
results.n_metabolites_before = nMetsBefore;
results.n_metabolites_after = numel(merged.mets);
results.compartments = sort_cellstr(merged.comps);
results.reactions = sort_cellstr(afterRxns);
results.removed_reactions = sort_cellstr(setdiff(beforeRxns, afterRxns));
results.deduplicated_reactions = sort_cellstr(flatten_indexed(duplicateRxns));
results.metabolites = sort_cellstr(merged.metNames);

[sortedRxns, order] = sort(afterRxns);
bounds = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    i = order(k);
    bounds{k} = struct( ...
        'reaction', sortedRxns{k}, ...
        'lower_bound', double(merged.lb(i)), ...
        'upper_bound', double(merged.ub(i)));
end
results.bounds = bounds;
results.stoichiometry = stoichiometry(merged);

end


function records = stoichiometry(model)
% Keyed by species name rather than metabolite id, matching run.py. char(1)
% joins the sort keys because it sorts below every character an identifier or
% a metabolite name can contain, so the ordering matches Python's tuple
% comparison.
[rowIdx, colIdx, coefficients] = find(model.S);

keys = cell(numel(rowIdx), 1);
for k = 1:numel(rowIdx)
    keys{k} = strjoin({model.rxns{colIdx(k)}, model.metNames{rowIdx(k)}}, char(1));
end
[~, order] = sort(keys);

records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'reaction', model.rxns{colIdx(i)}, ...
        'species', model.metNames{rowIdx(i)}, ...
        'coefficient', double(coefficients(i)));
end
end


function out = flatten_indexed(indexed)
% mergeCompartments documents its third output as the reactions deleted for
% being duplicates, but passes through contractModel's *third* output rather
% than its second: an indexed cell array with one entry per retained reaction,
% holding the ids folded into it separated by semicolons, and empty where
% nothing was. run.py gets a flat list of the ids that went, so the indexed
% form is flattened back to that here.
out = {};
if isempty(indexed)
    return
end
for k = 1:numel(indexed)
    entry = indexed{k};
    if isempty(entry)
        continue
    end
    parts = strsplit(char(entry), ';');
    for j = 1:numel(parts)
        name = strtrim(parts{j});
        if ~isempty(name)
            out{end+1} = name; %#ok<AGROW>
        end
    end
end
end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end
