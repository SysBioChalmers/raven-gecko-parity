function results = find_leak_metabolite_toy(ctx)
% MATLAB side of the findLeakMetabolite/find_leak_metabolite toy-model
% scenario.
%
% No shared fixture file: the model (A -> B -> 2A, C + D -> nothing) is
% small enough to build directly here, identically to run.py's
% _leak_model(). See scenario.yml for why each checkpoint is deterministic.
%
% findLeakMetabolite is LP-only, so this runs on RAVEN's default solver
% (glpk) -- no solver switch needed, unlike the MILP-based
% min_nr_fluxes_toy scenario.

ignoreAll = ctx.inputs.ignore_all(:);
ignoreByName = ctx.inputs.ignore_by_name(:);

model = leakModel();

results.produce_default = checkpoint(model, 'produce', {});
results.consume_pair = checkpoint(model, 'consume', {});
results.produce_all_ignored = checkpoint(model, 'produce', {'ignoreMets', ignoreAll});
results.produce_ignore_by_name = checkpoint(model, 'produce', ...
    {'ignoreMets', ignoreByName, 'isNames', true});
end


function model = leakModel()
model.mets = {'A';'B';'C';'D'};
model.metNames = {'alanine';'B';'C';'D'};
model.metComps = [1;1;1;1];
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'R1';'R2';'R3'};
model.rxnNames = model.rxns;
%       R1  R2  R3
model.S = sparse([-1  2   0;    % A
                    1 -1   0;    % B
                    0  0  -1;    % C
                    0  0  -1]);  % D
model.lb = [0;0;0];
model.ub = [1000;1000;1000];
model.rev = [0;0;0];
model.c = [0;0;0];
model.b = zeros(4,1);
end


function out = checkpoint(model, direction, extraArgs)
[sol, met] = findLeakMetabolite(model, direction, extraArgs{:});

if isempty(sol)
    out.status = 'infeasible';
    out.metabolites = {};
    out.fluxes = struct();
    return
end

out.status = 'optimal';
out.metabolites = sort(model.mets(met));

fluxes = struct();
for i = 1:numel(model.rxns)
    fluxes.(model.rxns{i}) = round(sol(i), 9);
end
out.fluxes = fluxes;
end
