function results = ec_fva_ectestgem(ctx)
% MATLAB side of the ecFVA scenario.
%
% One ecModel, one call to ecFVA, mapped back to the conventional model's reactions.
% Mirrors run.py; see scenario.yml for why R2's isozyme kcats are distinct and for the
% mechanism behind this scenario's one confirmed divergence (R2's own min/max flux).
%
% ecFVA always starts a parallel pool if one is not already running (parfor, no serial
% path), unlike geckopy's ec_fva, which this scenario tells to stay serial on this small
% model --- see scenario.yml's python_n_proc comment.

% The solver is named by the scenario rather than inherited, so that both sides are
% demonstrably solving with the same one. The preference is global and the nightly runs
% several scenarios in one MATLAB session, so whatever was set is put back on the way out.
previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcats = ctx.inputs.kcats;
kcatRxns = fieldnames(kcats);
for i = 1:numel(kcatRxns)
    idx = strcmp(ecModel.ec.rxns, kcatRxns{i});
    ecModel.ec.kcat(idx) = kcats.(kcatRxns{i});
    ecModel.ec.source(idx) = {'manual'};
end

ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

[minFlux, maxFlux] = ecFVA(ecModel, model);

n = numel(model.rxns);
records = cell(1, n);
for k = 1:n
    records{k} = struct('reaction', model.rxns{k}, ...
        'min_flux', double(minFlux(k)), 'max_flux', double(maxFlux(k)));
end
[~, order] = sort(model.rxns);
results.fva = records(order);

end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
