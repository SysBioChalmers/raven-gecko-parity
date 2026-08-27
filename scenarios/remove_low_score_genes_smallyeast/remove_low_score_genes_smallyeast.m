function results = remove_low_score_genes_smallyeast(ctx)
% MATLAB side of the low-score-gene-pruning scenario.
%
% removeLowScoreGenes takes geneScores as a numeric vector positionally
% aligned to model.genes, where the Python side takes a {gene_id: score}
% mapping; a gene absent from the map is represented here as NaN, which
% removeLowScoreGenes treats the same way absence is documented on the Python
% side --- unscored, never an individual removal candidate.
%
% The synthetic PGI rule is built with changeGrRules --- already
% cross-validated by change_gene_rules_smallyeast.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

synthetic = inputs.synthetic_rule;
model = changeGrRules(model, {char(synthetic.reaction)}, {char(synthetic.grRule)}, ...
    'replace', true);

targets = {'HXK', 'PFK', 'PGI'};
untouchedIdx = find(~ismember(model.rxns, targets));
beforeOther = containers.Map('KeyType', 'char', 'ValueType', 'any');
for k = 1:numel(untouchedIdx)
    i = untouchedIdx(k);
    beforeOther(model.rxns{i}) = clauses_of(model, i);
end

nGenesBefore = numel(model.genes);

scoreFields = fieldnames(inputs.scores);
geneScores = nan(numel(model.genes), 1);
for k = 1:numel(scoreFields)
    i = find(strcmp(model.genes, scoreFields{k}), 1);
    if ~isempty(i)
        geneScores(i) = double(inputs.scores.(scoreFields{k}));
    end
end

[reduced, remGenes] = removeLowScoreGenes(model, geneScores, ...
    'isozymeScoring', char(inputs.isozyme_scoring), ...
    'complexScoring', char(inputs.complex_scoring));

results.n_genes_before = nGenesBefore;
results.n_genes_after = numel(reduced.genes);
results.removed_genes = sort_cellstr(remGenes);

records = cell(1, numel(targets));
for k = 1:numel(targets)
    i = find(strcmp(reduced.rxns, targets{k}), 1);
    records{k} = struct('reaction', targets{k}, 'clauses', {clauses_of(reduced, i)});
end
results.reactions = records;

results.n_untouched_reactions_checked = beforeOther.Count;

% The point of the scenario: this should be empty on both sides.
unexpected = {};
keys = beforeOther.keys();
for k = 1:numel(keys)
    rid = keys{k};
    i = find(strcmp(reduced.rxns, rid), 1);
    if isempty(i) || ~isequal(beforeOther(rid), clauses_of(reduced, i))
        unexpected{end+1} = rid; %#ok<AGROW>
    end
end
results.unexpectedly_changed_reactions = sort_cellstr(unexpected);

end


function clauses = clauses_of(model, rxnIdx)
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
