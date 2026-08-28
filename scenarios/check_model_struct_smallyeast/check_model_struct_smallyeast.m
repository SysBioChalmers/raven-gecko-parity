function results = check_model_struct_smallyeast(ctx)
% MATLAB side of the model-structure-checking scenario.
%
% checkModelStruct, called with an output argument, collects every finding as
% a struct array (category, target, message) instead of throwing or printing
% --- confirmed from its own source: the collecting branch returns before the
% throw/warn branches run, regardless of throwErrors.
%
% checkModelStruct's own `category` field is not used: it is a coarse,
% order-sensitive classification over the free-text message (see the
% classify() helper below for exactly how two of the four checks here land
% under a category name unrelated to the check performed). Issues are
% reclassified by message text into the same four semantic categories
% check_model uses, and only target is otherwise compared; message itself
% is each side's own prose.
%
% Filtered to the four checks this scenario actually exercises --- see
% run.py and scenario.yml for why the rest of checkModelStruct's categories
% are not comparable at all, and why "duplicate" / multiple-objective are
% real overlaps left unasserted rather than untested.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

rewritten = inputs.rewritten_reaction;
model = changeRxns(model, {char(rewritten.reaction)}, {char(rewritten.equation)}, ...
    'eqnType', 1, 'allowNewMets', false);

% glyOUT's one metabolite is zeroed directly rather than through an equation
% string --- see scenario.yml for why.
i = find(strcmp(model.rxns, char(inputs.emptied_reaction)), 1);
model.S(:, i) = 0;

i = find(strcmp(model.rxns, char(inputs.objective_reaction)), 1);
model.c(i) = 0;

gpr = inputs.gpr_replaced;
model = changeGrRules(model, {char(gpr.reaction)}, {char(gpr.grRule)}, 'replace', true);

issues = checkModelStruct(model);

keys = {};
records = {};
for k = 1:numel(issues)
    category = classify(issues(k).message);
    if isempty(category)
        continue
    end
    keys{end+1} = join_key({category, issues(k).target}); %#ok<AGROW>
    records{end+1} = struct('category', category, 'entity', issues(k).target); %#ok<AGROW>
end

[~, order] = sort(keys);
records = records(order);

results.n_issues = numel(records);
results.issues = records;

end


function category = classify(msg)
% checkModelStruct's own `category` output (see issueCategory in
% queries/checkModelStruct.m) is a coarse, order-sensitive classification
% built from ad hoc substring matches over `msg`, checked in a fixed
% elseif order --- not a semantic label chosen per check. Two of the four
% checks this scenario exercises land under a category name that does not
% describe them at all: the empty-reaction check is tagged 'empty_id'
% only because its message contains the word "empty" (the same bucket
% catches blank-identifier checks elsewhere in the same function), and
% the no-objective check is tagged 'invalid_id' only because its message
% happens to mention "SBML" in an aside about export compliance, which is
% checked before the 'objective' branch is ever reached. The two orphan
% checks (metabolites, genes) both fall under a single shared 'unused'
% category rather than being told apart. None of this reflects a
% difference in what is actually detected --- RAVEN finds exactly the
% same four issues check_model does (see the ledger note on
% checkModelStruct) --- so this reclassifies by the specific, stable
% message text each of the four checks emits, to compare against
% check_model's own (semantically named, non-conflated) categories.
if contains(msg, 'are empty (no involved metabolites)')
    category = 'empty_reaction';
elseif contains(msg, 'never used in a reaction')
    category = 'orphan_metabolite';
elseif contains(msg, 'not associated to a reaction')
    category = 'orphan_gene';
elseif contains(msg, 'No objective function found')
    category = 'objective';
else
    category = '';
end
end


function key = join_key(parts)
key = strjoin(parts(:)', char(1));
end
