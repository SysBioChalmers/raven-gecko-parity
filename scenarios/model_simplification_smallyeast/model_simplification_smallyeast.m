function results = model_simplification_smallyeast(ctx)
% MATLAB side of the model-simplification scenario.
%
% simplifyModel returns the deleted reactions and metabolites; the Python
% umbrella entry point works in place and reports nothing. Both sides therefore
% take the difference between the model before and after, which is symmetric.
%
% deleteUnconstrained is switched off explicitly. It defaults to true and
% removes metabolites marked unconstrained --- a RAVEN convention with no
% analogue in a cobra model, which uses boundary reactions instead. Leaving the
% default on would compare a mode against nothing.

inputs = ctx.inputs;
modelPath = inputs.model;

cascadeModel = removeReactions(readYAMLmodel(modelPath), ...
    as_cellstr(inputs.cascade_removed_reactions));

results.zero_interval = checkpoint(readYAMLmodel(modelPath), {'deleteZeroInterval'});
results.composed = checkpoint(readYAMLmodel(modelPath), ...
    {'deleteZeroInterval', 'deleteInaccessible'});
results.composed_cascade = checkpoint(cascadeModel, ...
    {'deleteZeroInterval', 'deleteInaccessible'});
results.dead_end_alone = checkpoint(readYAMLmodel(modelPath), {'deleteInaccessible'});

end


function out = checkpoint(model, modes)
beforeRxns = model.rxns(:);
beforeMets = model.mets(:);

args = {'deleteUnconstrained', false};
for k = 1:numel(modes)
    args = [args, {modes{k}, true}]; %#ok<AGROW>
end
reduced = simplifyModel(model, args{:});

afterRxns = reduced.rxns(:);
afterMets = reduced.mets(:);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(afterRxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);

out.removed_reactions = sort_cellstr(setdiff(beforeRxns, afterRxns));
out.removed_metabolites = sort_cellstr(setdiff(beforeMets, afterMets));
out.reactions = sort_cellstr(afterRxns);
out.metabolites = sort_cellstr(afterMets);

% Keeping the chemistry under test as well as the census.
[sortedRxns, order] = sort(afterRxns);
bounds = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    i = order(k);
    bounds{k} = struct( ...
        'reaction', sortedRxns{k}, ...
        'lower_bound', double(reduced.lb(i)), ...
        'upper_bound', double(reduced.ub(i)));
end
out.bounds = bounds;
out.stoichiometry = stoichiometry(reduced);
end


function records = stoichiometry(model)
[rowIdx, colIdx, coefficients] = find(model.S);

keys = cell(numel(rowIdx), 1);
for k = 1:numel(rowIdx)
    keys{k} = strjoin({model.rxns{colIdx(k)}, model.mets{rowIdx(k)}}, char(1));
end
[~, order] = sort(keys);

records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'reaction', model.rxns{colIdx(i)}, ...
        'metabolite', model.mets{rowIdx(i)}, ...
        'coefficient', double(coefficients(i)));
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
