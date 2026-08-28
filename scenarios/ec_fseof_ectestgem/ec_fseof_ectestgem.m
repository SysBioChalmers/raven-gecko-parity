function results = ec_fseof_ectestgem(ctx)
% MATLAB side of the ecFSEOF scenario.
%
% Red on purpose --- see scenario.yml for the three confirmed, execution-measured
% divergences this checkpoint exists to demonstrate: the enforced-flux levels
% themselves, the candidate search space, and the target-selection criterion.

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

fseofAdapter = adapter;
fseofAdapter.params.bioRxn = char(ctx.inputs.bio_rxn);

fseof = ecFSEOF(ecModel, char(ctx.inputs.prod_target_rxn), char(ctx.inputs.cs_rxn), ...
    'nSteps', double(ctx.inputs.n_steps), 'modelAdapter', fseofAdapter);

results.enforced_levels = num2cell(reshape(double(fseof.alpha), 1, []));

% target_type is not compared: rxnTargets/transportTargets do not carry the OE/KD/KO
% label at all (only geneTargets does, in a different id space --- genes, not
% reactions), so there is nothing here to compare it against. The target *set* already
% demonstrates the divergence this scenario exists to show.
allTargets = [fseof.rxnTargets(:,1); fseof.transportTargets(:,1)];
results.targets = sort(reshape(allTargets, 1, []));

end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
