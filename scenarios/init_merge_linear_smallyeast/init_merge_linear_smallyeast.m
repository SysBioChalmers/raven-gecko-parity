function results = init_merge_linear_smallyeast(ctx)
% MATLAB side of the ftINIT linear-merge stage.
%
% mergeLinear returns the same four things as merge_linear --- reduced model,
% original reaction ids, a group id per original reaction, and a reversed flag
% per original reaction --- so the two line up directly.
%
% Multi-key sorts join their keys with char(1), which sorts below every
% character an identifier can contain, so they order exactly as Python's tuple
% comparison does.

inputs = ctx.inputs;
protected = as_cellstr(inputs.protected_reactions);

[reducedAll, origAll, groupAll, revAll] = mergeLinear(readYAMLmodel(inputs.model), {});
[reducedProt, origProt, groupProt, revProt] = mergeLinear(readYAMLmodel(inputs.model), protected);

results.merge_all = merge_checkpoint(reducedAll, origAll, groupAll, revAll);
results.merge_protected = merge_checkpoint(reducedProt, origProt, groupProt, revProt);
results.scores = score_checkpoint(inputs, reducedProt, origProt, groupProt);

end


function out = merge_checkpoint(reduced, origIds, groupIds, reversedRxns)
origIds = origIds(:);
groupIds = double(groupIds(:));
reversedRxns = logical(reversedRxns(:));

out.n_reactions_before = numel(origIds);
out.n_reactions_after = numel(reduced.rxns);

merged = groupIds ~= 0;
uniqueGroups = unique(groupIds(merged));
out.n_groups = numel(uniqueGroups);
out.n_merged = sum(merged);
out.n_reversed = sum(reversedRxns);

out.reactions = sort_cellstr(reduced.rxns);

% Sorted member lists, ordered by their first member: a canonical form for the
% partition that does not depend on how either side numbered its groups. The
% raw integers are deliberately not compared --- see scenario.yml.
groups = cell(1, numel(uniqueGroups));
firsts = cell(1, numel(uniqueGroups));
for k = 1:numel(uniqueGroups)
    members = sort_cellstr(origIds(groupIds == uniqueGroups(k)));
    groups{k} = members;
    firsts{k} = members{1};
end
[~, groupOrder] = sort(firsts);
groupRecords = cell(1, numel(groups));
indexOf = containers.Map('KeyType', 'char', 'ValueType', 'double');
for k = 1:numel(groups)
    members = groups{groupOrder(k)};
    groupRecords{k} = struct('members', {members});
    for j = 1:numel(members)
        indexOf(members{j}) = k;
    end
end
out.groups = groupRecords;

sortedOrig = sort(origIds);
records = cell(1, numel(sortedOrig));
for k = 1:numel(sortedOrig)
    if isKey(indexOf, sortedOrig{k})
        idx = indexOf(sortedOrig{k});
    else
        idx = 0;
    end
    records{k} = struct('reaction', sortedOrig{k}, 'group_index', idx);
end
out.group_index = records;

out.reversed_reactions = sort_cellstr(origIds(reversedRxns));

% The merge has to preserve the chemistry, not just the counts.
[sortedRxns, rxnOrder] = sort(reduced.rxns);
bounds = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    i = rxnOrder(k);
    bounds{k} = struct( ...
        'reaction', sortedRxns{k}, ...
        'lower_bound', double(reduced.lb(i)), ...
        'upper_bound', double(reduced.ub(i)));
end
out.bounds = bounds;
out.stoichiometry = stoichiometry(reduced);
end


function out = score_checkpoint(inputs, reduced, origIds, groupIds)
origIds = origIds(:);

% Every original reaction needs a score: the ones not named in the declaration
% are a genuine zero, which both sides lift to 0.01.
declared = inputs.scores;
origScores = zeros(numel(origIds), 1);
for k = 1:numel(origIds)
    name = matlab.lang.makeValidName(origIds{k});
    if isfield(declared, name)
        origScores(k) = double(declared.(name));
    end
end

% groupRxnScores takes a logical mask over the original reactions where
% run.py takes a list of ids.
toZero = ismember(origIds, as_cellstr(inputs.scores_to_zero));

newScores = groupRxnScores(reduced, origScores, origIds, double(groupIds(:)), toZero);

[sortedRxns, order] = sort(reduced.rxns);
records = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    records{k} = struct('reaction', sortedRxns{k}, 'score', double(newScores(order(k))));
end

out.n_reactions = numel(records);
out.scores = records;
end


function records = stoichiometry(model)
[rowIdx, colIdx, coefficients] = find(model.S);

keys = cell(numel(rowIdx), 1);
for k = 1:numel(rowIdx)
    keys{k} = join_key({model.rxns{colIdx(k)}, model.mets{rowIdx(k)}});
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
