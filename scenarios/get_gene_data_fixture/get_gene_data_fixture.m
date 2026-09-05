function results = get_gene_data_fixture(ctx)
% MATLAB side of the getGeneData/get_gene_data scenario.
%
% Calls the real getGeneData directly with a local GFF3 file path, bypassing
% downloadGenomeData entirely -- see scenario.yml for why.

geneTable = getGeneData(ctx.inputs.gff);

records = {};
for i = 1:height(geneTable)
    row.locus_tag = geneTable.locus_tag{i};
    row.old_locus_tag = geneTable.old_locus_tag{i};
    row.GeneID = geneTable.GeneID{i};
    row.gene_name = geneTable.gene_name{i};
    row.GenBank_protein = geneTable.GenBank_protein{i};
    row.UniProt = geneTable.UniProt{i};
    records{end+1} = row; %#ok<AGROW>
end
results.parsed = records;
end
