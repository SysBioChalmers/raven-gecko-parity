function results = merge_models_smallyeast(ctx)
% MATLAB side of the model-merging scenario.
%
% Same shape as run.py. mergeModels records provenance in rxnFrom/metFrom/
% geneFrom where the Python side uses notes["origin"]; both are reduced to a
% plain reaction-to-origin mapping, because the concept is shared even though
% the storage is not.
%
% Multi-key sorts join their keys with char(1), which sorts below every
% character an identifier can contain, so they order exactly as Python's tuple
% comparison does --- a printable separator would not, and this fixture is full
% of ids that are prefixes of one another ('ACO' and 'ACO_smallYeastBad').

first = readYAMLmodel(ctx.inputs.first);
second = readYAMLmodel(ctx.inputs.second);

originalIds = [first.rxns(:); second.rxns(:)];

merged = mergeModels({first, second});

results.model_id = char(merged.id);
results.n_reactions = numel(merged.rxns);
results.n_metabolites = numel(merged.mets);
if isfield(merged, 'genes')
    results.n_genes = numel(merged.genes);
else
    results.n_genes = 0;
end

results.reactions = sort_cellstr(merged.rxns);

% By difference from the two inputs rather than by matching on a suffix, so a
% reaction that already ended in the source model's id could not be miscounted.
renamed = merged.rxns(~ismember(merged.rxns, originalIds));
results.renamed_reactions = sort_cellstr(renamed);

results.metabolites = metabolite_records(merged);
if isfield(merged, 'genes')
    results.genes = sort_cellstr(merged.genes);
else
    results.genes = {};
end
results.reaction_origins = origins(merged);
results.gene_rules = gene_rules(merged);
results.stoichiometry = stoichiometry(merged);

end


function records = metabolite_records(model)
[~, order] = sort(model.mets);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'id', model.mets{i}, ...
        'name', model.metNames{i}, ...
        'compartment', model.comps{model.metComps(i)});
end
end


function records = origins(model)
[~, order] = sort(model.rxns);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    if isfield(model, 'rxnFrom') && numel(model.rxnFrom) >= i
        from = model.rxnFrom{i};
    else
        from = '';
    end
    records{k} = struct('reaction', model.rxns{i}, 'origin', char(from));
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
out = reshape(sort(values(:)), 1, []);
if isempty(out)
    out = {};
end
end
