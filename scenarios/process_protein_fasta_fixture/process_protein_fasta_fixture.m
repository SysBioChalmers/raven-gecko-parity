function results = process_protein_fasta_fixture(ctx)
% MATLAB side of the processProteinFastaFile/process_protein_fasta_file
% scenario. Calls the real function directly (it transforms and writes a
% file, unlike walkFluxes/followChanged).

proteinIds = ctx.inputs.protein_ids(:);
headerValues = ctx.inputs.header_values(:);
geneTable = table(proteinIds, headerValues, 'VariableNames', ...
    {'GenBank_protein', ctx.inputs.header_col});

outDir = tempname;
mkdir(outDir);
evalc('outFile = processProteinFastaFile(ctx.inputs.faa, geneTable, ctx.inputs.header_col, outDir);');

fastaStruct = readFasta(outFile);
records = {};
for i = 1:numel(fastaStruct)
    row.header = fastaStruct(i).Header;
    row.sequence = fastaStruct(i).Sequence;
    records{end+1} = row; %#ok<AGROW>
end
results.processed = records;

rmdir(outDir, 's');
end
