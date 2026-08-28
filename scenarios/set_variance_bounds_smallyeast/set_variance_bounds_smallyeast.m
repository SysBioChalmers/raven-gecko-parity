function results = set_variance_bounds_smallyeast(ctx)
% MATLAB side of the variance-bounds scenario.
%
% setParam's "var" mode and set_variance_bounds take the same three numbers
% per reaction --- a measured value, a percent, the reaction itself --- and
% compute the same sign-dependent band. Only this one mode of setParam is
% covered; see scenario.yml for why the other six are not.
%
% Reactions outside the two checkpoints are fingerprinted before and after:
% setParam mutates by reaction index, and a miscounted index would move a
% bound on the wrong reaction, which only checking "everything else" catches.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

distinctRxns = sort(fieldnames(inputs.distinct.values));
broadcastRxns = as_cellstr(inputs.broadcast.reactions);
touched = union(distinctRxns, broadcastRxns);

untouchedIdx = find(~ismember(model.rxns, touched));
beforeOther = containers.Map('KeyType', 'char', 'ValueType', 'any');
for k = 1:numel(untouchedIdx)
    i = untouchedIdx(k);
    beforeOther(model.rxns{i}) = [model.lb(i), model.ub(i)];
end

distinctValues = zeros(numel(distinctRxns), 1);
for k = 1:numel(distinctRxns)
    distinctValues(k) = double(inputs.distinct.values.(distinctRxns{k}));
end
model = setParam(model, 'var', distinctRxns, distinctValues, double(inputs.distinct.percent));

model = setParam(model, 'var', broadcastRxns, double(inputs.broadcast.value), ...
    double(inputs.broadcast.percent));

results.n_untouched_reactions_checked = beforeOther.Count;

unexpected = {};
keys = beforeOther.keys();
for k = 1:numel(keys)
    rid = keys{k};
    i = find(strcmp(model.rxns, rid), 1);
    if isempty(i) || ~isequal(beforeOther(rid), [model.lb(i), model.ub(i)])
        unexpected{end+1} = rid; %#ok<AGROW>
    end
end
results.unexpectedly_changed_reactions = sort_cellstr(unexpected);

results.distinct = bounds_of(model, distinctRxns);
results.broadcast = bounds_of(model, sort(broadcastRxns));

end


function records = bounds_of(model, rxnIds)
rxnIds = rxnIds(:)';
records = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    i = find(strcmp(model.rxns, rxnIds{k}), 1);
    records{k} = struct( ...
        'reaction', rxnIds{k}, ...
        'lower_bound', double(model.lb(i)), ...
        'upper_bound', double(model.ub(i)));
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
