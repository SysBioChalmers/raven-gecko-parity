function results = ec_model_full_yeastgem(ctx)
% MATLAB side of the genome-scale ecModel pipeline scenario (Tier 4).
%
% Runs the full non-DLKcat pipeline on GECKO's own yeast-GEM tutorial model. See
% scenario.yml for why DLKcat is out of scope and for the one confirmed divergence
% (EC-code validation strictness) this scenario asserts. Unlike the Python side, no
% eccodes or BRENDA-format workaround is needed here: readYAMLmodel and
% loadBRENDAdata.m already read yeast-GEM.yml and GECKO's own BRENDA files natively.

previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

results.expansion.conv_counts = struct( ...
    'reactions', numel(model.rxns), ...
    'metabolites', numel(model.mets), ...
    'genes', numel(model.genes));

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

results.expansion.ec_counts = struct( ...
    'ec_rxns', numel(ecModel.ec.rxns), ...
    'enzymes', numel(ecModel.ec.enzymes), ...
    'genes', numel(ecModel.ec.genes), ...
    'eccodes_populated', sum(~cellfun(@isempty, ecModel.ec.eccodes)));
results.expansion.ec_rxns = reshape(sort(ecModel.ec.rxns(:)), 1, []);
results.expansion.enzymes = reshape(sort(ecModel.ec.enzymes(:)), 1, []);

kcatList = fuzzyKcatMatching(ecModel, [], adapter);
ecModel = selectKcatValue(ecModel, kcatList);
ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

n = numel(ecModel.ec.rxns);
rows = cell(1, n);
for i = 1:n
    src = '';
    if ~isempty(ecModel.ec.source{i})
        src = lower(ecModel.ec.source{i});
    end
    rows{i} = struct('reaction', ecModel.ec.rxns{i}, 'kcat', double(ecModel.ec.kcat(i)), 'source', src);
end
[~, order] = sort(ecModel.ec.rxns);
rows = rows(order);

poolIdx = strcmp(ecModel.rxns, 'prot_pool_exchange');
results.kcats.pool_ub = double(ecModel.ub(poolIdx));
results.kcats.nonzero_count = sum(ecModel.ec.kcat > 0);
results.kcats.rows = rows;

end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
