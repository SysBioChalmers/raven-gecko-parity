function results = rename_model_genes_smallyeast(ctx)
% MATLAB side of the renameModelGenes/rename_model_genes scenario.
%
% Calls the real renameModelGenes directly (unlike walkFluxes/followChanged,
% this function actually transforms and returns the model, so there's no
% need to reimplement its internals).

model = readYAMLmodel(ctx.inputs.model);

geneIds = ctx.inputs.gene_ids(:);
geneNames = ctx.inputs.gene_names(:);
geneTable = table(geneIds, geneNames, 'VariableNames', ...
    {ctx.inputs.from_col, ctx.inputs.to_col});

evalc('model = renameModelGenes(model, geneTable, ctx.inputs.from_col, ctx.inputs.to_col);');

results.renamed = checkpoint(model);
end


function out = checkpoint(model)
out.all_gene_ids = sort(model.genes);

reactionGenes = struct();
for i = 1:numel(model.rxns)
    geneIdx = find(model.rxnGeneMat(i, :));
    if isempty(geneIdx)
        continue
    end
    reactionGenes.(model.rxns{i}) = sort(model.genes(geneIdx));
end
out.reaction_genes = reactionGenes;
end
