function results = remove_bad_reactions_toy(ctx)
% MATLAB side of the removeBadRxns/remove_bad_reactions toy-model scenario.
%
% No shared fixture file: the model (A -> B -> 2A, both with a real carbon
% formula) is small enough to build directly here, identically to run.py's
% _bad_model(). See scenario.yml for why this fixture is deterministic.
%
% removeBadRxns is LP-only (via findLeakMetabolite), so this runs on
% RAVEN's default solver (glpk).

ignoreBoth = ctx.inputs.ignore_both(:);

% balanceElements is passed explicitly as {'C'} rather than left at its
% default {'C','P','S','N','O'}: getElementalBalance requires every
% requested element to actually appear somewhere in the model's formulas,
% and this toy model (formula 'C1' throughout) only ever has carbon. See
% scenario.yml / remove_bad_reactions's own docstring for why this
% validation is not replicated on the Python side.
results.default_removes_r2 = checkpoint(badModel(), {'balanceElements', {'C'}});
results.ignoring_both_mets_removes_nothing = checkpoint(badModel(), ...
    {'ignoreMets', ignoreBoth, 'balanceElements', {'C'}});
end


function model = badModel()
model.mets = {'A';'B'};
model.metNames = {'A';'B'};
model.metComps = [1;1];
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.metFormulas = {'C1';'C1'};
model.rxns = {'R1';'R2'};
model.rxnNames = model.rxns;
%       R1  R2
model.S = sparse([-1  2;    % A
                    1 -1]); % B
model.lb = [0;0];
model.ub = [1000;1000];
model.rev = [0;0];
model.c = [0;0];
model.b = zeros(2,1);
end


function out = checkpoint(model, extraArgs)
[newModel, removedRxns] = removeBadRxns(model, extraArgs{:});
out.removed = sort(removedRxns);
out.remaining = sort(newModel.rxns);
end
