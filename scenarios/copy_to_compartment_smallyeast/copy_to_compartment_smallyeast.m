function results = copy_to_compartment_smallyeast(ctx)
% MATLAB side of the compartment-copying scenario.
%
% copyToComps takes a cell array of target compartments where the Python side
% takes one; the scenario names one, which both signatures express.
%
% New reactions and metabolites are derived by difference from the model before
% and after, not from the return value: copyToComps returns only the updated
% model, so the difference is the one quantity both sides can state.

inputs = ctx.inputs;

results.copy = checkpoint(inputs, false);
results.move = checkpoint(inputs, true);

end


function out = checkpoint(inputs, deleteOriginal)
model = readYAMLmodel(inputs.model);
beforeRxns = model.rxns(:);
beforeMets = model.mets(:);

target = char(inputs.target_compartment);
updated = copyToComps(model, {target}, ...
    'rxns', as_cellstr(inputs.reactions), ...
    'deleteOriginal', logical(deleteOriginal), ...
    'compNames', {char(inputs.target_compartment_name)});

afterRxns = updated.rxns(:);
afterMets = updated.mets(:);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(afterRxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);

out.new_reactions = sort_cellstr(setdiff(afterRxns, beforeRxns));
out.removed_reactions = sort_cellstr(setdiff(beforeRxns, afterRxns));
out.new_metabolites = species_records(updated, ~ismember(afterMets, beforeMets));

out.compartments = compartment_records(updated);
out.reactions = sort_cellstr(afterRxns);
% By species and compartment, not by id --- see scenario.yml.
out.metabolites = species_records(updated, true(numel(afterMets), 1));

[sortedRxns, order] = sort(afterRxns);
bounds = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    i = order(k);
    bounds{k} = struct( ...
        'reaction', sortedRxns{k}, ...
        'lower_bound', double(updated.lb(i)), ...
        'upper_bound', double(updated.ub(i)));
end
out.bounds = bounds;

out.gene_rules = gene_rules(updated);
out.stoichiometry = stoichiometry(updated);
end


function records = compartment_records(model)
[~, order] = sort(model.comps);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    if isfield(model, 'compNames') && numel(model.compNames) >= i
        name = model.compNames{i};
    else
        name = '';
    end
    records{k} = struct('id', model.comps{i}, 'name', name);
end
end


function records = species_records(model, mask)
% Metabolites as (name, compartment), the identity that survives both naming
% conventions. char(1) joins the sort key because it sorts below every
% character a name can contain, so the ordering matches Python's tuple
% comparison.
idx = find(mask(:)');
keys = cell(1, numel(idx));
for k = 1:numel(idx)
    i = idx(k);
    keys{k} = join_key({model.comps{model.metComps(i)}, model.metNames{i}});
end
[~, order] = sort(keys);

records = cell(1, numel(idx));
for k = 1:numel(order)
    i = idx(order(k));
    records{k} = struct( ...
        'name', model.metNames{i}, ...
        'compartment', model.comps{model.metComps(i)});
end
if isempty(records)
    records = {};
end
end


function records = gene_rules(model)
[~, order] = sort(model.rxns);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
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

    records{k} = struct('reaction', model.rxns{i}, 'clauses', {clauses});
end
end


function records = stoichiometry(model)
[rowIdx, colIdx, coefficients] = find(model.S);

keys = cell(numel(rowIdx), 1);
for k = 1:numel(rowIdx)
    keys{k} = join_key({model.rxns{colIdx(k)}, ...
        model.comps{model.metComps(rowIdx(k))}, model.metNames{rowIdx(k)}});
end
[~, order] = sort(keys);

records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'reaction', model.rxns{colIdx(i)}, ...
        'species', model.metNames{rowIdx(i)}, ...
        'compartment', model.comps{model.metComps(rowIdx(i))}, ...
        'coefficient', double(coefficients(i)));
end
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
