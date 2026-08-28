function results = okp_kcat_ectestgem(ctx)
% MATLAB side of the OpenKineticsPredictor (OKP) scenario, mirroring run.py.
%
% findMetSmiles, writeOpenKineticsPredictorInput (both filter branches) and
% readOpenKineticsPredictorOutput, on one ecModel built from ecTestGEM. See
% scenario.yml for scope (CSV boundary only, not the real OKP REST API) and for
% [GECKO #437], the real indexing bug this scenario's write checkpoint found,
% confirmed and fixed --- this scenario's own MATLAB result was generated against a
% worktree with that fix applied ahead of merge.
%
% findMetSmiles and writeOpenKineticsPredictorInput both resolve fixture/output paths
% through the adapter's own params.path, unlike their Python counterparts, which each
% take an explicit path. A *copy* of the adapter --- ModelAdapter is a value class, so
% this cannot affect the original, same pattern as kcat_chain_ectestgem.m --- has its
% params.path redirected to this scenario's own data/ folder for those calls.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);
ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

okpAdapter = adapter;
okpAdapter.params.path = ctx.inputs.scenario_root;

[results.smiles, ecModel] = checkpoint_smiles(ecModel, okpAdapter);
[results.write, ecModel] = checkpoint_write(ecModel, okpAdapter);
results.read_output = checkpoint_read(ecModel, ctx.inputs, okpAdapter);

end


% --------------------------------------------------------------------------- %
% smiles: findMetSmiles
% --------------------------------------------------------------------------- %

function [out, ecModel] = checkpoint_smiles(ecModel, okpAdapter)
ecModel = findMetSmiles(ecModel, 'modelAdapter', okpAdapter, 'verbose', false);
out = smiles_snapshot(ecModel);
end


function out = smiles_snapshot(ecModel)
n = numel(ecModel.mets);
records = cell(1, n);
for k = 1:n
    s = '';
    if ~isempty(ecModel.metSmiles{k})
        s = ecModel.metSmiles{k};
    end
    records{k} = struct('met', ecModel.mets{k}, 'smiles', s);
end
[~, order] = sort(ecModel.mets);
records = records(order);
out = struct();
for k = 1:n
    out.(records{k}.met) = records{k}.smiles;
end
end


% --------------------------------------------------------------------------- %
% write: writeOpenKineticsPredictorInput
% --------------------------------------------------------------------------- %

function [out, ecModel] = checkpoint_write(ecModel, okpAdapter)
% ec.rxns order on this fixture is [R2_EXP_1, R2_EXP_2, R2_REV_EXP_1, R2_REV_EXP_2,
% R3, R5] (confirmed by direct execution, identical on both sides). Requesting
% {R2_EXP_1, R2_EXP_2, R3} skips the two REV entries sitting in between --- exactly
% the subset shape [GECKO #437]'s bug mishandled, so this checkpoint doubles as its
% regression check.
withSmilesMask = ismember(ecModel.ec.rxns, {'R2_EXP_1', 'R2_EXP_2', 'R3'});
writeOpenKineticsPredictorInput(ecModel, 'ecRxns', withSmilesMask, ...
    'modelAdapter', okpAdapter, 'onlyWithSmiles', true, 'overwrite', true);
out.with_smiles = read_csv_pairs(okpAdapter);

% m2 (R5's substrate) deliberately loses its SMILES here, so the two calls below
% exercise onlyWithSmiles' two branches on something real: with the filter off, R5's
% entry survives with a 'None' placeholder; with it on (the default), the same entry
% is dropped instead of appearing at all.
ecModel.metSmiles(strcmp(ecModel.mets, 'm2c')) = {''};
fullMask = ismember(ecModel.ec.rxns, {'R2_EXP_1', 'R2_EXP_2', 'R3', 'R5'});

writeOpenKineticsPredictorInput(ecModel, 'ecRxns', fullMask, ...
    'modelAdapter', okpAdapter, 'onlyWithSmiles', false, 'overwrite', true);
out.after_clearing_m2_without_filter = read_csv_pairs(okpAdapter);

writeOpenKineticsPredictorInput(ecModel, 'ecRxns', fullMask, ...
    'modelAdapter', okpAdapter, 'onlyWithSmiles', true, 'overwrite', true);
out.after_clearing_m2_with_filter = read_csv_pairs(okpAdapter);
end


function out = read_csv_pairs(okpAdapter)
csvFile = fullfile(okpAdapter.params.path, 'data', 'OKP.csv');
fID = fopen(csvFile);
raw = textscan(fID, '%s %s', 'Delimiter', ',', 'HeaderLines', 1);
fclose(fID);
delete(csvFile);
pairs = strcat(raw{1}, ',', raw{2});
out = reshape(sort(pairs), 1, []);
end


% --------------------------------------------------------------------------- %
% read_output: readOpenKineticsPredictorOutput
% --------------------------------------------------------------------------- %

function out = checkpoint_read(ecModel, inputs, okpAdapter)
kcatList = readOpenKineticsPredictorOutput(ecModel, 'outFile', inputs.okp_result_path, ...
    'modelAdapter', okpAdapter);
n = numel(kcatList.rxns);
records = cell(1, n);
for k = 1:n
    % MATLAB's kcatSource carries an 'OKP-' prefix geckopy's source column does not
    % (see scenario.yml) --- recorded verbatim, not normalized to a shared token, so
    % the split stays visible in the comparison rather than being hidden by the
    % checkpoint itself.
    records{k} = struct('reaction', kcatList.rxns{k}, 'gene', kcatList.genes{k}, ...
        'substrate', kcatList.substrates{k}, 'kcat', double(kcatList.kcats(k)), ...
        'source', kcatList.kcatSource{k});
end
keys = cellfun(@(r) [r.reaction char(1) r.gene], records, 'UniformOutput', false);
[~, order] = sort(keys);
out.rows = records(order);
end
