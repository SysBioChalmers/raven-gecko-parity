function results = change_gene_rules_smallyeast(ctx)
% MATLAB side of the gene-rule-setting scenario.
%
% changeGrRules takes parallel arrays of reaction id and GPR string where
% change_gene_reaction_rules takes a mapping; the scenario's one reaction per
% checkpoint is handled the same either way.
%
% Only replace mode and append mode onto a reaction that already carries a
% GPR are covered --- see scenario.yml for why append mode onto an empty GPR
% is a confirmed divergence (raven-gecko-parity#12) rather than a checkpoint
% here.

inputs = ctx.inputs;

replaced = fieldnames(inputs.replaced);
results.replace = checkpoint(inputs.model, replaced, ...
    struct_values(inputs.replaced, replaced), true);

appended = fieldnames(inputs.appended);
results.append = checkpoint(inputs.model, appended, ...
    struct_values(inputs.appended, appended), false);

end


function out = checkpoint(modelPath, rxnIds, newRules, replace)
model = readYAMLmodel(modelPath);
beforeGenes = genes_of(model);

updated = changeGrRules(model, rxnIds, newRules, 'replace', replace);

afterGenes = genes_of(updated);

out.n_genes_before = numel(beforeGenes);
out.n_genes_after = numel(afterGenes);
out.created_genes = sort_cellstr(setdiff(afterGenes, beforeGenes));

[sortedRxnIds] = sort(rxnIds);
records = cell(1, numel(sortedRxnIds));
for k = 1:numel(sortedRxnIds)
    i = find(strcmp(updated.rxns, sortedRxnIds{k}), 1);
    records{k} = fingerprint(updated, i);
end
out.reactions = records;
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

record = struct('reaction', model.rxns{rxnIdx}, 'clauses', {clauses});
end


function out = genes_of(model)
if isfield(model, 'genes')
    out = model.genes(:);
else
    out = {};
end
end


function out = struct_values(s, fieldOrder)
% Reads the fields of s back out in fieldOrder, as a cellstr --- the harness's
% jsondecode gives a scalar struct for a JSON object, so fields() and direct
% indexing is how the declared mapping is recovered on this side.
out = cell(1, numel(fieldOrder));
for k = 1:numel(fieldOrder)
    out{k} = char(s.(fieldOrder{k}));
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
