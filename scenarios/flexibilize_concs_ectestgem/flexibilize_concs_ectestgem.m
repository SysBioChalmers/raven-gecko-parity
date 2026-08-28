function results = flexibilize_concs_ectestgem(ctx)
% MATLAB side of the flexibilize-concentrations scenario.
%
% Two independent checkpoints, mirroring run.py: flux_data (loadFluxData +
% constrainFluxData, 'loose' and percentage-variance mode, no LP solve involved) and
% flexibilize (flexibilizeEnzConcs on enzyme_usage_ectestgem's own R2/R4-blocked,
% single-bottleneck fixture, reused rather than re-derived). See scenario.yml for the
% one confirmed divergence, in flexibilizeEnzConcs's post-loop refinement pass only.
%
% TestGEMAdapter.m's own bioRxn ('R4', "Not relevant") and c_source ('E1', not a real
% reaction id here) are not used as-is: both loadFluxData/constrainFluxData/
% flexibilizeEnzConcs resolve these through the adapter rather than taking them as
% direct arguments, so a *copy* of the adapter (value class, same pattern as
% kcat_chain_ectestgem's kcatAdapter) carries the corrected values instead.

previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

fixAdapter = adapter;
fixAdapter.params.bioRxn = char(ctx.inputs.bio_rxn);
fixAdapter.params.c_source = char(ctx.inputs.c_source);

results.flux_data = checkpoint_flux_data(model, adapter, fixAdapter, ctx.inputs);
results.flexibilize = checkpoint_flexibilize(model, adapter, fixAdapter, ctx.inputs);

end


% --------------------------------------------------------------------------- %
% flux_data: loadFluxData + constrainFluxData
% --------------------------------------------------------------------------- %

function out = checkpoint_flux_data(model, adapter, fixAdapter, inputs)
fluxData = loadFluxData('fluxDataFile', char(inputs.flux_data_path), 'modelAdapter', adapter);

out.parsed.conds = reshape(fluxData.conds, 1, []);
% num2cell, not reshape alone: jsonencode collapses a 1x1 (single-condition) numeric
% array to a bare scalar instead of a one-element JSON array, the same pitfall
% docs/scenarios.md already warns about for 1x1 struct arrays, but for plain numbers.
out.parsed.p_tot = num2cell(reshape(double(fluxData.Ptot), 1, []));
out.parsed.gr_rate = num2cell(reshape(double(fluxData.grRate), 1, []));
n = size(fluxData.exchFluxes, 1);
rows = cell(1, n);
for k = 1:n
    rows{k} = reshape(double(fluxData.exchFluxes(k, :)), 1, []);
end
out.parsed.exch_fluxes = rows;
out.parsed.exch_mets = reshape(fluxData.exchMets, 1, []);
out.parsed.exch_rxn_ids = reshape(fluxData.exchRxnIDs, 1, []);

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);
out.loose = constrained_bounds(ecModel, fluxData, 'loose', fixAdapter);

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);
out.pct = constrained_bounds(ecModel, fluxData, double(inputs.pct_variance), fixAdapter);
end


function out = constrained_bounds(ecModel, fluxData, looseStrictFlux, fixAdapter)
constrained = constrainFluxData(ecModel, 'fluxData', fluxData, 'condition', 1, ...
    'maxMinGrowth', 'max', 'looseStrictFlux', looseStrictFlux, 'modelAdapter', fixAdapter);
out.S1 = rxn_bounds(constrained, 'S1');
out.S2 = rxn_bounds(constrained, 'S2');
out.R5 = rxn_bounds(constrained, 'R5');
end


function out = rxn_bounds(model, rxnID)
idx = strcmp(model.rxns, rxnID);
out.lb = double(model.lb(idx));
out.ub = double(model.ub(idx));
end


% --------------------------------------------------------------------------- %
% flexibilize: flexibilizeEnzConcs
% --------------------------------------------------------------------------- %

function out = checkpoint_flexibilize(model, adapter, fixAdapter, inputs)
r2Idx = strcmp(model.rxns, 'R2');
r4Idx = strcmp(model.rxns, 'R4');
model.lb(r2Idx) = 0; model.ub(r2Idx) = 0;
model.lb(r4Idx) = 0; model.ub(r4Idx) = 0;

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcats = inputs.flex_kcats;
kcatRxns = fieldnames(kcats);
for i = 1:numel(kcatRxns)
    idx = strcmp(ecModel.ec.rxns, kcatRxns{i});
    ecModel.ec.kcat(idx) = kcats.(kcatRxns{i});
    ecModel.ec.source(idx) = {'manual'};
end

protData = loadProtData(1, [], [], adapter);
ecModel = fillEnzConcs(ecModel, protData);
ecModel = constrainEnzConcs(ecModel);
ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

sol0 = solveLP(ecModel);
out.base_growth = double(sol0.f);

[ecModelFlex, flexEnz] = flexibilizeEnzConcs(ecModel, 'expGrowth', double(inputs.exp_growth), ...
    'foldChange', double(inputs.fold_change), 'iterPerEnzyme', double(inputs.iter_per_enzyme), ...
    'modelAdapter', fixAdapter, 'verbose', false);

n = numel(flexEnz.uniprotIDs);
flexed = cell(1, n);
for i = 1:n
    flexed{i} = struct('protein', flexEnz.uniprotIDs{i}, ...
        'old_conc', double(flexEnz.oldConcs(i)), ...
        'flex_conc', double(flexEnz.flexConcs(i)), ...
        'ratio_incr', double(flexEnz.ratioIncr(i)), ...
        'frequence', double(flexEnz.frequence(i)));
end
out.flexed = flexed;

solF = solveLP(ecModelFlex);
out.final_growth = double(solF.f);
end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
