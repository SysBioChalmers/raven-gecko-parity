function results = apply_condition_smallyeast(ctx)
% MATLAB side of the condition-prelude scenario.
%
% applyCondition's prelude.reset_exchanges step is direction-aware: the
% condition's own value is forwarded straight to getExchangeRxns as its
% reactionType filter (getExchangeRxns(model, cond.prelude.reset_exchanges)),
% so reset_exchanges: "out" resets only the reactions getExchangeRxns
% classifies as 'out' --- those where the boundary metabolite is the
% reaction's product, smallYeast's five *OUT reactions. apply_condition
% cannot make this distinction at all (cobra has no concept of RAVEN's
% in/out split) and resets every exchange reaction regardless of which
% direction was named --- see run.py and
% raven_toolbox/conditions/apply.py's own docstring, which says so
% plainly.
%
% Confirmed on the Python side before this file was written: the same
% condition takes smallYeast from unable to grow at all (glcIN, o2IN,
% ethIN all shut) to a growth rate of ~90, because those three reactions
% get reset open even though only the "out" direction was named.

inputs = ctx.inputs;

previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver)); %#ok<NASGU>
setRavenSolver(char(inputs.matlab_solver));

model = readYAMLmodel(inputs.model);

cond = struct();
cond.prelude = struct();
cond.prelude.reset_exchanges = char(inputs.reset_exchanges);
model = applyCondition(model, cond);

% Alphabetical already --- kept as a literal list rather than sorted at
% runtime so it is visibly the same list run.py sorts on the Python side.
unitExchange = {'acOUT','biomassOUT','co2OUT','ethIN','ethOUT','glcIN','glyOUT','o2IN'};
records = cell(1, numel(unitExchange));
for k = 1:numel(unitExchange)
    i = find(strcmp(model.rxns, unitExchange{k}), 1);
    records{k} = struct('reaction', unitExchange{k}, 'lb', model.lb(i), 'ub', model.ub(i));
end
results.exchange_bounds_after = records;

% sol.f is the maximised objective directly, not its negation --- see
% close_model_smallyeast.m's flux_range() for why (an empirical
% calibration, not a full derivation: the final sign-relevant step lives
% in renameparams, which is not part of the RAVEN repo).
sol = solveLP(model);
results.growth_after = sol.f;

end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
