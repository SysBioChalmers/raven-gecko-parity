function results = init_scores_smallyeast(ctx)
% MATLAB side of the ftINIT scoring stage.
%
% scoreComplexModel does both stages in one call and returns geneScores and
% rxnScores; run.py runs them as two functions. The result document splits them
% the same way on both sides.
%
% arrayData is assembled here rather than by a parser, so that the two sides
% are handed the same table: first occurrence of a duplicated gene wins, and
% the table is restricted to genes the model has. Both are properties of the
% fixture, not of either toolbox --- see scenario.yml.

inputs = ctx.inputs;

model = readYAMLmodel(inputs.model);
modelGenes = sort(model.genes(:));

[genes, levels] = read_expression(inputs.expression, modelGenes);

arrayData.genes = genes;
arrayData.tissues = {'tutorial'};
arrayData.celltypes = {'tutorial'};
arrayData.levels = levels;
% A scalar threshold is expanded to one per gene inside scoreComplexModel.
arrayData.threshold = double(inputs.threshold);

[rxnScores, geneScores] = scoreComplexModel(model, [], arrayData, 'tutorial', ...
    'noGeneScore', double(inputs.no_gene_score), ...
    'isozymeScoring', char(inputs.isozyme_scoring), ...
    'complexScoring', char(inputs.complex_scoring));

results.gene_scores = gene_score_checkpoint(model, modelGenes, geneScores);
results.reaction_scores = reaction_score_checkpoint(model, rxnScores);

end


function out = gene_score_checkpoint(model, modelGenes, geneScores)
% geneScores is indexed by model.genes, which is not sorted; the records are
% emitted in sorted gene order to match run.py.
records = cell(1, numel(modelGenes));
nScored = 0;
for k = 1:numel(modelGenes)
    i = find(strcmp(model.genes, modelGenes{k}), 1);

    % A gene with no expression value comes back as NaN. Reported as a flag
    % plus a zero rather than as NaN: jsonencode writes NaN as null while the
    % Python side canonicalises it to the string "NaN", so an absent score
    % would read as a difference between the two harnesses.
    score = 0;
    hasScore = false;
    if ~isempty(i) && ~isnan(geneScores(i))
        score = double(geneScores(i));
        hasScore = true;
        nScored = nScored + 1;
    end

    records{k} = struct('gene', modelGenes{k}, 'has_score', hasScore, 'score', score);
end

out.n_genes = numel(modelGenes);
out.n_scored = nScored;
out.scores = records;
end


function out = reaction_score_checkpoint(model, rxnScores)
[sortedRxns, order] = sort(model.rxns);

records = cell(1, numel(sortedRxns));
for k = 1:numel(sortedRxns)
    records{k} = struct('reaction', sortedRxns{k}, 'score', double(rxnScores(order(k))));
end

out.n_reactions = numel(records);
out.scores = records;
end


function [genes, levels] = read_expression(path, wanted)
% Two columns, tab separated: gene, level. First occurrence wins, and only
% genes the model has are kept.
fid = fopen(path, 'r');
if fid < 0
    error('init_scores:noExpression', 'cannot read %s', path);
end
closeFile = onCleanup(@() fclose(fid));
columns = textscan(fid, '%s%f', 'Delimiter', '\t');

allGenes = columns{1};
allLevels = columns{2};

keep = false(numel(allGenes), 1);
seen = containers.Map('KeyType', 'char', 'ValueType', 'logical');
for k = 1:numel(allGenes)
    gene = strtrim(allGenes{k});
    if ~any(strcmp(wanted, gene)) || isKey(seen, gene)
        continue
    end
    seen(gene) = true;
    keep(k) = true;
end

genes = allGenes(keep);
levels = allLevels(keep);
end
