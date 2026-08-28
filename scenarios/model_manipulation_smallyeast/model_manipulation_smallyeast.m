function results = model_manipulation_smallyeast(ctx)
% MATLAB side of the structural-manipulation chain.
%
% Same three checkpoints as run.py, each from a fresh read of the model so a
% difference in one does not cascade into the next. The shape must match
% run.py exactly; where the two disagree, that is the finding.
%
% Two conventions carry the risk here:
%
%   * Ordering. Everything except the `sorted` checkpoint is sorted by
%     identifier, because model order is not a specification. Multi-key sorts
%     join the keys with char(1) --- lower than any character appearing in an
%     identifier --- so that they order exactly as Python's tuple comparison
%     does. Joining with a printable separator would not: '|' is above '_', so
%     ACS|x would sort after ACS_EXP_1|y where Python puts ACS first.
%   * grRules are compared as gene sets, not as strings. expandModel finishes
%     by calling standardizeGrRules, which brackets complexes; the Python side
%     joins a clause with " and ". Diffing the strings would report that
%     formatting difference every night.

modelPath = ctx.inputs.model;

results.irrev  = irrev_checkpoint(readYAMLmodel(modelPath));
results.expand = expand_checkpoint(readYAMLmodel(modelPath));
results.sorted = sorted_checkpoint(readYAMLmodel(modelPath));

end


function out = irrev_checkpoint(model)
irrevModel = convertToIrrev(model);

isReverse = endsWith(irrevModel.rxns, '_REV');
out.n_reactions = numel(irrevModel.rxns);
out.n_reverse = sum(isReverse);
out.reverse_reactions = sort_cellstr(irrevModel.rxns(isReverse));
out.reactions = reaction_records(irrevModel);
out.gene_rules = gene_rules(irrevModel);
out.stoichiometry = stoichiometry(irrevModel);
end


function out = expand_checkpoint(model)
originalRxns = model.rxns;
newModel = expandModel(model);

% The expanded reactions are the ones that were not there before. Derived by
% set difference rather than by matching '_EXP_', so a reaction that already
% carried that suffix in the input could not be miscounted.
added = setdiff(newModel.rxns, originalRxns);

out.n_reactions = numel(newModel.rxns);
out.n_added = numel(added);
out.added_reactions = sort_cellstr(added);
out.reactions = reaction_records(newModel);
out.gene_rules = gene_rules(newModel);
out.stoichiometry = stoichiometry(newModel);
end


function out = sorted_checkpoint(model)
newModel = sortIdentifiers(model);

% Model order, not sorted order: this checkpoint's whole content is the order
% sortIdentifiers produced, and sorting it here would compare the harness
% against itself.
out.reactions = row(newModel.rxns);
out.metabolites = row(newModel.mets);
if isfield(newModel, 'genes')
    out.genes = row(newModel.genes);
else
    out.genes = {};
end
out.compartments = row(newModel.comps);
end


function records = reaction_records(model)
[~, order] = sort(model.rxns);

records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'id', model.rxns{i}, ...
        'name', model.rxnNames{i}, ...
        'lower_bound', double(model.lb(i)), ...
        'upper_bound', double(model.ub(i)), ...
        'objective_coefficient', double(model.c(i)));
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

    % Genes sorted within a clause, then clauses sorted between themselves:
    % the comparison is about which genes catalyse the reaction, not about
    % the order the rule happened to list them in.
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
% char(1) sorts below every character an identifier can contain, so joining on
% it reproduces Python's element-by-element tuple/list ordering --- including
% the case where one key is a prefix of another.
key = strjoin(parts(:)', char(1));
end


function out = sort_cellstr(values)
out = row(sort(values(:)));
end


function out = row(values)
% jsonencode writes a cell array as a JSON array whichever way it is oriented,
% but keeping every list a row makes the intent explicit and keeps an empty
% list an empty array rather than a null.
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
end
