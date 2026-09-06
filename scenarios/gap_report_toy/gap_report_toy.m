function results = gap_report_toy(ctx) %#ok<INUSD>
% MATLAB side of the gapReport/gap_report toy-model scenario.
%
% No shared fixture file: the model (a working glc->pyr->co2 chain, R3
% blocked for lack of an upstream source, an isolated orphan metabolite z,
% and the P/Q unbalanced-cycle leak) is small enough to build directly here,
% identically to run.py's _gap_report_model(). See scenario.yml for why
% canProduceWithoutInput/canConsumeWithoutOutput and templateModels are not
% exercised.
%
% gapReport is LP-only (via haveFlux/checkProduction), so this runs on
% RAVEN's default solver (glpk).

model = gapsModel();
evalc('[noFluxRxns, noFluxRxnsRelaxed, subGraphs, notProducedIdx, minToConnectRaw, neededForProductionMat] = gapReport(model);');

results.no_flux_reactions = sort(noFluxRxns);
results.no_flux_reactions_relaxed = sort(noFluxRxnsRelaxed);
results.subgraph_sizes = sort(sum(subGraphs), 'descend');

notProduced = model.mets(notProducedIdx);
results.not_produced_metabolites = sort(notProduced);

needed = struct();
for i = 1:numel(notProduced)
    row = notProduced(logical(neededForProductionMat(i, :)));
    needed.(notProduced{i}) = sort(row);
end
results.needed_for_production = needed;

minToConnect = cell(numel(minToConnectRaw), 1);
for i = 1:numel(minToConnectRaw)
    entry = minToConnectRaw{i};
    metId = entry(1:find(entry == '[', 1) - 1);
    connectsStr = regexp(entry, 'connects (\d+) metabolites', 'tokens');
    item.metabolite = metId;
    item.connects = str2double(connectsStr{1}{1});
    minToConnect{i} = item;
end
results.min_to_connect = minToConnect;
end


function model = gapsModel()
model.id = 'gaps';
model.name = 'Gaps';
model.mets = {'glc';'pyr';'co2';'x';'y';'z';'P';'Q'};
model.metNames = model.mets;
model.metComps = ones(8, 1);
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'EX_glc';'R1';'R2';'DM_co2';'R3';'R4';'R5'};
model.rxnNames = model.rxns;
%       EX_glc R1  R2  DM_co2 R3  R4  R5
model.S = sparse([
    -1     -1   0   0      0   0   0;   % glc
     0      1  -1   0      0   0   0;   % pyr
     0      0   1  -1      0   0   0;   % co2
     0      0   0   0     -1   0   0;   % x
     0      0   0   0      1   0   0;   % y
     0      0   0   0      0   0   0;   % z
     0      0   0   0      0  -1   2;   % P
     0      0   0   0      0   1  -1]); % Q
% EX_glc is a real uptake/excretion (bounded, not unconstrained); R1/R2 are
% plain irreversible; DM_co2 is a demand; R3/R4/R5 as in run.py.
model.lb = [-10; 0; 0; 0; 0; 0; 0];
model.ub = [1000; 1000; 1000; 1000; 1000; 1000; 1000];
model.rev = [1; 0; 0; 0; 0; 0; 0];
model.c = zeros(7, 1);
model.b = zeros(8, 1);
end
