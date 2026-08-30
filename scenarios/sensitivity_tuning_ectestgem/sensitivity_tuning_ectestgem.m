function results = sensitivity_tuning_ectestgem(ctx)
% MATLAB side of the sensitivity-tuning scenario.
%
% Three independent checkpoints, mirroring run.py. See scenario.yml for the
% confirmed divergence (sigmaFitter's returned-model bug, fixed as GECKO#433).

previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

fixAdapter = adapter;
fixAdapter.params.bioRxn = char(ctx.inputs.bio_rxn);

results.sensitivity_tuning = checkpoint_sensitivity_tuning(model, adapter, fixAdapter, ctx.inputs);
results.sigma_fitter = checkpoint_sigma_fitter(model, adapter, ctx.inputs);
results.truncate_values = checkpoint_truncate_values(ctx.inputs);

end


% --------------------------------------------------------------------------- %
% sensitivity_tuning: sensitivityTuning
% --------------------------------------------------------------------------- %

function ecModel = blocked_single_route_model(model, adapter, kcats)
r2Idx = strcmp(model.rxns, 'R2');
r4Idx = strcmp(model.rxns, 'R4');
model.lb(r2Idx) = 0; model.ub(r2Idx) = 0;
model.lb(r4Idx) = 0; model.ub(r4Idx) = 0;

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcatRxns = fieldnames(kcats);
for i = 1:numel(kcatRxns)
    idx = strcmp(ecModel.ec.rxns, kcatRxns{i});
    ecModel.ec.kcat(idx) = kcats.(kcatRxns{i});
    ecModel.ec.source(idx) = {'manual'};
end
end


function out = checkpoint_sensitivity_tuning(model, adapter, stAdapter, inputs)
ecModel = blocked_single_route_model(model, adapter, inputs.sens_kcats);
ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

sol0 = solveLP(ecModel);
out.base_growth = double(sol0.f);

[ecModelTuned, tunedKcats] = sensitivityTuning(ecModel, ...
    'desiredGrowthRate', double(inputs.sens_desired_growth), ...
    'modelAdapter', stAdapter, 'verbose', false);

n = numel(tunedKcats.rxns);
tuned = cell(1, n);
for i = 1:n
    tuned{i} = struct('reaction', tunedKcats.rxns{i}, 'enzymes', tunedKcats.enzymes{i}, ...
        'old_kcat', double(tunedKcats.oldKcat(i)), 'new_kcat', double(tunedKcats.newKcat(i)), ...
        'source', tunedKcats.source{i});
end
out.tuned = tuned;

solF = solveLP(ecModelTuned);
out.final_growth = double(solF.f);
end


% --------------------------------------------------------------------------- %
% sigma_fitter: sigmaFitter
% --------------------------------------------------------------------------- %

function out = checkpoint_sigma_fitter(model, adapter, inputs)
ecModel = blocked_single_route_model(model, adapter, inputs.sigma_kcats);
ecModel.c = double(strcmp(ecModel.rxns, char(inputs.bio_rxn)));
ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

[fittedModel, sigma] = sigmaFitter(ecModel, ...
    'growthRate', double(inputs.sigma_growth_rate), ...
    'Ptot', double(inputs.sigma_p_tot), 'f', double(inputs.sigma_f), ...
    'makePlot', false, 'modelAdapter', adapter);

out.sigma = double(sigma);
poolIdx = strcmp(fittedModel.rxns, 'prot_pool_exchange');
out.model_pool_ub = double(fittedModel.ub(poolIdx));
end


% --------------------------------------------------------------------------- %
% truncate_values: truncateValues
% --------------------------------------------------------------------------- %

function out = checkpoint_truncate_values(inputs)
vals = num2cell(reshape(double(inputs.truncate_values), 1, []));
out = truncateValues(vals, 1:numel(vals));
end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
