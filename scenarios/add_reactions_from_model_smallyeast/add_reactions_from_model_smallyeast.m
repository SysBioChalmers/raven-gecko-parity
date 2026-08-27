function results = add_reactions_from_model_smallyeast(ctx)
% MATLAB side of the reaction-transfer scenario.
%
% addRxnsGenesMets and add_reactions_from_model take the same three arguments
% and the same three options. The draft is prepared identically on both sides:
% the reactions are removed along with the metabolites and genes they leave
% unused, so that adding them back has to create both.
%
% What was added is derived by difference from the model before and after,
% which is the quantity both sides can state.

inputs = ctx.inputs;

results.with_genes = checkpoint(inputs, true);
results.without_genes = checkpoint(inputs, false);

end


function out = checkpoint(inputs, addGene)
transferred = as_cellstr(inputs.transferred_reactions);

draft = removeReactions(readYAMLmodel(inputs.model), transferred, ...
    'removeUnusedMets', true, 'removeUnusedGenes', true);

beforeRxns = draft.rxns(:);
beforeMets = draft.mets(:);
beforeGenes = genes_of(draft);

source = readYAMLmodel(inputs.model);
draft = addRxnsGenesMets(draft, source, transferred, ...
    'addGene', logical(addGene), ...
    'rxnNote', char(inputs.note), ...
    'confidence', double(inputs.confidence));

afterRxns = draft.rxns(:);
afterMets = draft.mets(:);
afterGenes = genes_of(draft);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(afterRxns);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);
out.n_genes_before = numel(beforeGenes);
out.n_genes_after = numel(afterGenes);

addedRxns = setdiff(afterRxns, beforeRxns);
out.added_reactions = sort_cellstr(addedRxns);
out.added_metabolites = sort_cellstr(setdiff(afterMets, beforeMets));
out.added_genes = sort_cellstr(setdiff(afterGenes, beforeGenes));

out.reactions = sort_cellstr(afterRxns);
out.metabolites = sort_cellstr(afterMets);
out.genes = sort_cellstr(afterGenes);

[sortedRxns, order] = sort(afterRxns);
bounds = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    i = order(k);
    bounds{k} = struct( ...
        'reaction', sortedRxns{k}, ...
        'lower_bound', double(draft.lb(i)), ...
        'upper_bound', double(draft.ub(i)));
end
out.bounds = bounds;

out.gene_rules = gene_rules(draft);
out.transfer_annotations = transfer_annotations(draft, sort(addedRxns));
out.stoichiometry = stoichiometry(draft);
end


function records = transfer_annotations(model, addedRxns)
% The provenance a curator later reads off a transferred reaction. RAVEN keeps
% it in rxnNotes and rxnConfidenceScores where the Python side keeps it in the
% reaction's notes; same two values either way.
addedRxns = addedRxns(:)';
records = cell(1, numel(addedRxns));
for k = 1:numel(addedRxns)
    i = find(strcmp(model.rxns, addedRxns{k}), 1);

    note = '';
    if isfield(model, 'rxnNotes') && numel(model.rxnNotes) >= i
        note = model.rxnNotes{i};
    end
    confidence = 0;
    if isfield(model, 'rxnConfidenceScores') && numel(model.rxnConfidenceScores) >= i ...
            && ~isnan(model.rxnConfidenceScores(i))
        confidence = double(model.rxnConfidenceScores(i));
    end

    records{k} = struct('reaction', addedRxns{k}, 'note', note, 'confidence', confidence);
end
if isempty(records)
    records = {};
end
end


function out = genes_of(model)
if isfield(model, 'genes')
    out = model.genes(:);
else
    out = {};
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
