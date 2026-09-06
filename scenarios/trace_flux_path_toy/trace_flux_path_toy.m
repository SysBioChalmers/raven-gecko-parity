function results = trace_flux_path_toy(ctx) %#ok<INUSD>
% MATLAB side of the traceFluxPath/trace_flux_path toy-model scenario.
%
% No shared fixture file: the model (R1 -> B/ATP junction, B splitting 70/30
% into R2a/R2b, an ATP-only dead end via R5) is small enough to build
% directly here, identically to run.py's _junction_model(). See scenario.yml
% for why each checkpoint is deterministic.
%
% traceFluxPath has no solver dependency at all (it only reads S and the
% given flux vector), so this needs no solver switch.

model = junctionModel();
fluxes = [10; 7; 3; 7; 3; 10]; % R1, R2a, R2b, R3, R4, R5, in model.rxns order

results.direct_junction = checkpoint(model, fluxes, 'R1', 'R2a', {});
results.two_hop_majority = checkpoint(model, fluxes, 'R1', 'R3', {});
results.minority_branch = checkpoint(model, fluxes, 'R1', 'R4', {});
results.currency_blocked_by_default = checkpoint(model, fluxes, 'R1', 'R5', {});
results.currency_route_when_allowed = checkpoint(model, fluxes, 'R1', 'R5', {'traceMaterial', false});
results.max_hops_prunes = checkpoint(model, fluxes, 'R1', 'R3', {'maxHops', 1});
end


function model = junctionModel()
model.mets = {'A';'B';'C';'E';'D';'D2';'atp_c'};
model.metNames = {'A';'B';'C';'E';'D';'D2';'ATP'};
model.metComps = ones(7,1);
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'R1';'R2a';'R2b';'R3';'R4';'R5'};
model.rxnNames = model.rxns;
%       R1  R2a R2b R3  R4  R5
model.S = sparse([
    -1   0   0   0   0   0;   % A
     1  -1  -1   0   0   0;   % B
     0   1   0  -1   0   0;   % C
     0   0   1   0  -1   0;   % E
     0   0   0   1   1   0;   % D
     0   0   0   0   0   1;   % D2
     1   0   0   0   0  -1]); % atp_c
model.lb = zeros(6,1);
model.ub = repmat(1000,6,1);
model.rev = zeros(6,1);
model.c = zeros(6,1);
model.b = zeros(7,1);
end


function out = checkpoint(model, fluxes, fromRxn, toRxn, extraArgs)
[pathRxns, pathMets, cumFrac] = traceFluxPath(model, fluxes, fromRxn, toRxn, ...
    'verbose', false, extraArgs{:});
out.reactions = pathRxns;
out.metabolites = pathMets;
out.cumulative_fraction = cumFrac;
end
