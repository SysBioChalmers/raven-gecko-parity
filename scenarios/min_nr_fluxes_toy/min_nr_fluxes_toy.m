function results = min_nr_fluxes_toy(ctx)
% MATLAB side of the getMinNrFluxes/get_min_nr_fluxes toy-model scenario.
%
% No shared fixture file: the model (X <- source1, X <- source2, X ->
% demand fixed at 5) is small enough to build directly here, identically to
% run.py's _two_source_model(). See scenario.yml for why.
%
% getMinNrFluxes needs a MILP-capable solver; glpk (RAVEN's default) can't
% do it and errors outright, so this switches to scip for the duration.

prevSolver = getpref('RAVEN','solver');
setRavenSolver('scip');
cleanup = onCleanup(@() setRavenSolver(prevSolver));

toMinimize = ctx.inputs.to_minimize(:);
scores = double(ctx.inputs.scores(:));

results.tie_broken_by_scores = checkpoint(two_source_model(), toMinimize, scores);

infeasibleModel = two_source_model();
infeasibleModel.ub(strcmp(infeasibleModel.rxns,'source1')) = 0;
infeasibleModel.ub(strcmp(infeasibleModel.rxns,'source2')) = 0;
results.infeasible = checkpoint(infeasibleModel, toMinimize, scores);
end


function model = two_source_model()
model.mets = {'X'};
model.metNames = {'X'};
model.metComps = [1];
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'source1';'source2';'demand'};
model.rxnNames = model.rxns;
model.S = sparse([1 1 -1]);
model.lb = [0;0;5];
model.ub = [1000;1000;5];
model.rev = [0;0;0];
model.c = [0;0;0];
model.b = zeros(1,1);
end


function out = checkpoint(model, toMinimize, scores)
[x, I, exitFlag] = getMinNrFluxes(model, toMinimize, 'scores', scores);

if exitFlag ~= 1
    out.status = 'infeasible';
    out.active = {};
    out.fluxes = struct();
    return
end

out.status = 'optimal';
out.active = sort(toMinimize(I));

fluxes = struct();
for i = 1:numel(model.rxns)
    fluxes.(model.rxns{i}) = round(x(i), 9);
end
out.fluxes = fluxes;
end
