function results = change_reaction_equations_smallyeast(ctx)
% MATLAB side of the reaction-rewriting scenario.
%
% changeRxns takes parallel arrays of reaction id and equation string where
% change_reaction_equations takes a mapping; the scenario's two reactions are
% handled the same either way. Both mutate the named reactions in place and
% touch nothing else about them, which is most of what this scenario checks.
%
% The whole model is fingerprinted, not just the two changed reactions: the
% claim is that everything else is untouched, and that is only evidence if
% the rest of the model is looked at too.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

rxnIds = fieldnames(inputs.equations);
equationList = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    equationList{k} = char(inputs.equations.(rxnIds{k}));
end

untouchedIdx = find(~ismember(model.rxns, rxnIds));
beforeOther = containers.Map('KeyType', 'char', 'ValueType', 'any');
for k = 1:numel(untouchedIdx)
    i = untouchedIdx(k);
    beforeOther(model.rxns{i}) = fingerprint(model, i);
end

beforeMets = model.mets(:);

updated = changeRxns(model, rxnIds, equationList, ...
    'eqnType', 1, ...
    'compartment', char(inputs.compartment), ...
    'allowNewMets', logical(inputs.allow_new_mets));

afterMets = updated.mets(:);

results.n_reactions = numel(updated.rxns);
results.n_metabolites_before = numel(beforeMets);
results.n_metabolites_after = numel(afterMets);
results.created_metabolites = sort_cellstr(setdiff(afterMets, beforeMets));

[sortedRxnIds, order] = sort(rxnIds);
changedRecords = cell(1, numel(sortedRxnIds));
for k = 1:numel(sortedRxnIds)
    i = find(strcmp(updated.rxns, sortedRxnIds{k}), 1);
    changedRecords{k} = fingerprint(updated, i);
end
results.changed_reactions = changedRecords;

results.n_untouched_reactions_checked = untouchedIdx_count(beforeOther);

% The point of the scenario: this should be empty on both sides. A reaction id
% here rather than a bare pass/fail flag says which reaction moved when the
% docstrings promised none would.
unexpected = {};
keys = beforeOther.keys();
for k = 1:numel(keys)
    rid = keys{k};
    i = find(strcmp(updated.rxns, rid), 1);
    if isempty(i) || ~isequal(beforeOther(rid), fingerprint(updated, i))
        unexpected{end+1} = rid; %#ok<AGROW>
    end
end
results.unexpectedly_changed_reactions = sort_cellstr(unexpected);

end


function n = untouchedIdx_count(m)
n = m.Count;
end


function record = fingerprint(model, rxnIdx)
if isfield(model, 'grRules') && ~isempty(model.grRules{rxnIdx})
    clauses = grRuleToDNF(model.grRules{rxnIdx});
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
    [~, order] = sort(keys);
    clauses = clauses(order);
end

subsystem = '';
if isfield(model, 'subSystems') && ~isempty(model.subSystems{rxnIdx})
    entry = model.subSystems{rxnIdx};
    if iscell(entry)
        entry = entry{1};
    end
    subsystem = char(entry);
end

metIdx = find(model.S(:, rxnIdx) ~= 0)';
[~, order] = sort(model.mets(metIdx));
metIdx = metIdx(order);
stoich = cell(1, numel(metIdx));
for k = 1:numel(metIdx)
    % full(): indexing a sparse S yields a sparse scalar, and jsonencode
    % refuses one ("Unable to encode sparse objects").
    stoich{k} = {model.mets{metIdx(k)}, double(full(model.S(metIdx(k), rxnIdx)))};
end

record = struct( ...
    'reaction', model.rxns{rxnIdx}, ...
    'name', model.rxnNames{rxnIdx}, ...
    'lower_bound', double(model.lb(rxnIdx)), ...
    'upper_bound', double(model.ub(rxnIdx)), ...
    'objective_coefficient', double(model.c(rxnIdx)), ...
    'subsystem', subsystem, ...
    'clauses', {clauses}, ...
    'stoichiometry', {stoich});
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
