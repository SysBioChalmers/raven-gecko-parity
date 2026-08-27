function results = remove_genes_smallyeast(ctx)
% MATLAB side of the gene-removal scenario.
%
% removeGenes returns only the updated model; run.py reports the blocked set
% from what remove_genes returns directly. removeGenes has no such return
% value, so the harness derives it from the same single pass instead: under
% removeBlockedRxns=false a blocked reaction is exactly one whose bounds
% became (0, 0) and were not already; under removeBlockedRxns=true it is
% exactly the set of removed reactions. Either way it is read off the one
% call each checkpoint already makes, not a second one.
%
% Only the three touched reactions (PGI, PFK, HXK) are inspected in detail:
% the rest of the model is untouched by construction.

inputs = ctx.inputs;
touched = {'PGI', 'PFK', 'HXK'};

results.constrained = checkpoint(inputs, touched, false);
results.removed = checkpoint(inputs, touched, true);

end


function out = checkpoint(inputs, touched, removeBlockedRxns)
model = readYAMLmodel(inputs.model);
genesToRemove = as_cellstr(inputs.removed_genes);

beforeRxns = model.rxns(:);
beforeMets = model.mets(:);
beforeGenes = model.genes(:);
wasZero = (model.lb == 0 & model.ub == 0);

reduced = removeGenes(model, genesToRemove, ...
    'removeUnusedMets', true, ...
    'removeBlockedRxns', removeBlockedRxns, ...
    'standardizeRules', true);

afterRxns = reduced.rxns(:);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(afterRxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(reduced.mets);
out.n_genes_before = numel(beforeGenes);
out.n_genes_after = numel(reduced.genes);

removedRxns = setdiff(beforeRxns, afterRxns);
out.removed_reactions = sort_cellstr(removedRxns);

if removeBlockedRxns
    out.blocked_reactions = sort_cellstr(removedRxns);
else
    [~, keptIdx] = ismember(afterRxns, beforeRxns);
    nowZero = (reduced.lb == 0 & reduced.ub == 0);
    out.blocked_reactions = sort_cellstr(afterRxns(nowZero & ~wasZero(keptIdx)));
end

records = cell(1, numel(touched));
for k = 1:numel(touched)
    records{k} = reaction_state(reduced, touched{k});
end
out.reactions = records;
end


function record = reaction_state(model, rxnId)
i = find(strcmp(model.rxns, rxnId), 1);
if isempty(i)
    record = struct('reaction', rxnId, 'present', false, ...
        'lower_bound', 0.0, 'upper_bound', 0.0, 'clauses', {{}});
    return
end

% As sorted DNF clauses rather than the raw grRule string: a bracketing or
% case difference in how each side renders a rule back to text would
% otherwise read as a divergence in gene logic.
if isfield(model, 'grRules') && ~isempty(model.grRules{i})
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
    [~, order] = sort(keys);
    clauses = clauses(order);
end

record = struct( ...
    'reaction', rxnId, ...
    'present', true, ...
    'lower_bound', double(model.lb(i)), ...
    'upper_bound', double(model.ub(i)), ...
    'clauses', {clauses});
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
