function results = duplicate_reactions_smallyeast(ctx)
% MATLAB side of the duplicate-detection scenario.
%
% findDuplicateRxns returns every pairwise combination of a duplicate set as
% reaction *indices*; run.py gets groups of reaction objects. Both are reduced
% to sorted lists of reaction ids here. The pairs within a set form a clique,
% so recovering the groups from them is a union-find over the pairs and loses
% nothing.

modelPath = ctx.inputs.model;

results.plain_any_direction = checkpoint(readYAMLmodel(modelPath), true);
results.plain_same_direction = checkpoint(readYAMLmodel(modelPath), false);
results.expanded_any_direction = checkpoint(expandModel(readYAMLmodel(modelPath)), true);
results.expanded_same_direction = checkpoint(expandModel(readYAMLmodel(modelPath)), false);

end


function out = checkpoint(model, ignoreDirection)
pairs = findDuplicateRxns(model, 'ignoreDirection', ignoreDirection);

groups = groups_from_pairs(pairs, numel(model.rxns), model.rxns);

out.n_reactions = numel(model.rxns);
out.n_groups = numel(groups);

total = 0;
records = cell(1, numel(groups));
for k = 1:numel(groups)
    records{k} = struct('members', {groups{k}});
    total = total + numel(groups{k});
end

% Total reactions implicated, not the number of groups: a group of three and
% three groups of two are different findings.
out.n_duplicate_reactions = total;
out.groups = records;
end


function groups = groups_from_pairs(pairs, nRxns, rxnIds)
groups = {};
if isempty(pairs)
    return
end

parent = 1:nRxns;
for k = 1:size(pairs, 1)
    a = root(parent, pairs(k, 1));
    b = root(parent, pairs(k, 2));
    if a ~= b
        parent(b) = a;
    end
end

roots = zeros(1, nRxns);
for i = 1:nRxns
    roots(i) = root(parent, i);
end

members = {};
firsts = {};
for r = unique(roots)
    idx = find(roots == r);
    if numel(idx) < 2
        continue
    end
    ids = reshape(sort(rxnIds(idx)), 1, []);
    members{end+1} = ids; %#ok<AGROW>
    firsts{end+1} = ids{1}; %#ok<AGROW>
end

if isempty(members)
    return
end

% Ordered by first member, matching run.py.
[~, order] = sort(firsts);
groups = members(order);
end


function r = root(parent, i)
r = i;
while parent(r) ~= r
    r = parent(r);
end
end
