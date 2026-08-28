function results = close_model_smallyeast(ctx)
% MATLAB side of the model-closing scenario.
%
% closeModel and close_model agree on which reactions are "unit exchange"
% (coefficients summing to 1 in absolute value) but close them through
% mechanisms that share no structure at all: closeModel appends a new
% boundary metabolite --- in a fresh 'b' compartment --- to each one, and
% never touches its bounds; close_model leaves the model's metabolites and
% compartments untouched and zeroes the reaction's own bounds directly.
%
% Despite that, both close the SAME reactions in the sense that matters,
% confirmed here by optimising each one's own flux to its minimum and
% maximum after closure, rather than by comparing either side's own
% (structurally incompatible) representation of "closed". closeModel's
% mechanism works because of how solveLP itself is built (solver/solveLP.m):
% fluxes and one slack variable per metabolite are solved together as a
% single vector, the slack bounded by model.b and pinned by the equality
% S*v - slack = 0. closeModel appends exactly the scalar 0 as the new
% boundary metabolite's model.b entry; since nothing else ever touches that
% metabolite, its slack is pinned to 0 too, which forces the one reaction
% touching it to zero flux --- even though that reaction's own lb/ub are
% left exactly as they were. Confirmed empirically before this file was
% written: closeModel's own output leaves every affected reaction's bounds
% untouched, and a solve still shows the same zero flux capacity as the
% Python side, which zeroes those bounds directly instead.

inputs = ctx.inputs;

% The solver is named by the scenario rather than inherited --- see
% gapfill_connect_smallyeast for why (a silent solver mismatch would compare
% solvers, not toolboxes). The preference is global and the nightly runs
% several scenarios in one MATLAB session, so whatever was set is put back
% on the way out.
previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver)); %#ok<NASGU>
setRavenSolver(char(inputs.matlab_solver));

model = readYAMLmodel(inputs.model);

% smallYeast ships every carbon/oxygen source shut (lb=ub=0); closing an
% already-closed exchange proves nothing, so glucose and oxygen uptake are
% opened first.
i = find(strcmp(model.rxns, 'glcIN'), 1);
model.ub(i) = double(inputs.glc_uptake);
i = find(strcmp(model.rxns, 'o2IN'), 1);
model.ub(i) = double(inputs.o2_uptake);

unitExchange = {};
for i = 1:numel(model.rxns)
    if full(sum(abs(model.S(:,i)))) == 1
        unitExchange{end+1} = model.rxns{i}; %#ok<AGROW>
    end
end
unitExchange = sort_cellstr(unitExchange);

sol = solveLP(model);
results.growth_before = sol.f;

controlId = char(inputs.control_reaction);
[controlMinBefore, controlMaxBefore] = flux_range(model, controlId);

closedModel = closeModel(model);

sol = solveLP(closedModel);
results.growth_after = sol.f;

records = cell(1, numel(unitExchange));
for k = 1:numel(unitExchange)
    [lo, hi] = flux_range(closedModel, unitExchange{k});
    records{k} = struct('reaction', unitExchange{k}, 'min_flux', lo, 'max_flux', hi);
end

[controlMinAfter, controlMaxAfter] = flux_range(closedModel, controlId);

results.unit_exchange_reactions = row(unitExchange);
results.closed_reactions = records;
results.control_reaction = controlId;
results.control_min_before = controlMinBefore;
results.control_max_before = controlMaxBefore;
results.control_min_after = controlMinAfter;
results.control_max_after = controlMaxAfter;

end


function [minFlux, maxFlux] = flux_range(model, rxnId)
% model is a value here, not a reference --- mutating model.c below never
% touches the caller's own copy, so there is nothing to restore afterward.
%
% solveLP's sign convention here is taken from measurement, not derived:
% solver/solveLP.m minimises model.c*-1 with osense=1, which by RAVEN's own
% source should make solution.f the NEGATIVE of max(model.c'*v) --- but
% renameparams, which turns osense into the 'min'/'max' string the
% underlying solver actually receives, is not part of RAVEN's own source
% (not found anywhere under the RAVEN repo) and could not be read to
% confirm that chain the rest of the way. Calibrated instead against a
% known-correct reference: solveLP(model) on this same model with its own
% unmodified, positive, maximise-biomass model.c returns solution.f
% directly equal to +growth_before (verified against the Python side's own
% FBA answer for the same bounds) --- no negation needed for a
% "maximise this" objective. c(i)=1 mirrors that same "maximise" sign, so
% its solution.f is the maximum directly; c(i)=-1 asks it to maximise the
% negated reaction, so the true minimum is the negation of what comes back.
i = find(strcmp(model.rxns, rxnId), 1);

c = zeros(numel(model.rxns), 1);
c(i) = 1;
model.c = c;
sol = solveLP(model);
maxFlux = sol.f;

c(i) = -1;
model.c = c;
sol = solveLP(model);
minFlux = -sol.f;
end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end


function out = row(values)
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end
