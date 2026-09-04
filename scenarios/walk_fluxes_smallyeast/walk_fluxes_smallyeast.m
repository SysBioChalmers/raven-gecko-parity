function results = walk_fluxes_smallyeast(ctx)
% MATLAB side of the walkFluxes/walk_fluxes navigation scenario.
%
% Reimplements walkFluxes.m's per-step neighbour computation (its lines
% computing allNeighbors/seenRxns from model.S) rather than calling
% walkFluxes itself, which blocks on interactive input() and has nothing to
% return. This is the same approach duplicate_reactions_smallyeast takes for
% findDuplicateRxns's pairwise output: reduce the real function's internal
% logic to the structured groups a scenario can compare, without touching
% RAVEN source.

model = readYAMLmodel(ctx.inputs.model);

fluxes = zeros(numel(model.rxns), 1);
fnames = fieldnames(ctx.inputs.fluxes);
for i = 1:numel(fnames)
    idx = find(strcmp(model.rxns, fnames{i}));
    fluxes(idx) = ctx.inputs.fluxes.(fnames{i});
end

results.atpx_neighbors = walk_step(model, fluxes, ctx.inputs.start_rxn, ...
    ctx.inputs.cutoff, ctx.inputs.max_per_met);
end


function out = walk_step(model, fluxes, startRxn, cutoff, maxPerMet)
rxnIdx = find(strcmp(model.rxns, startRxn));
f = fluxes(rxnIdx);

col = full(model.S(:, rxnIdx));
nonzeroMets = find(abs(col) > 0);

seenRxns = containers.Map('KeyType', 'double', 'ValueType', 'double');
allNeighbors = [];
groups = {};

for mi = 1:numel(nonzeroMets)
    m = nonzeroMets(mi);
    netF = col(m) * f;
    if abs(netF) < cutoff, continue; end

    if netF < 0
        role = 'consumed';
    else
        role = 'produced';
    end

    row = full(model.S(m, :));
    carry = find(abs(row .* fluxes') > cutoff);
    carry = carry(carry ~= rxnIdx);
    if isempty(carry), continue; end

    [~, si] = sort(abs(fluxes(carry)), 'descend');
    carry = carry(si(1:min(end, maxPerMet)));

    neighbors = {};
    for ci = 1:numel(carry)
        nr = carry(ci);
        neighNetF = row(nr) * fluxes(nr);
        if neighNetF < 0
            neighRole = 'consumes';
        else
            neighRole = 'produces';
        end

        if isKey(seenRxns, nr)
            n = seenRxns(nr);
        else
            n = numel(allNeighbors) + 1;
            seenRxns(nr) = n;
            allNeighbors(end + 1) = nr; %#ok<AGROW>
        end

        nb.number = n;
        nb.reaction = model.rxns{nr};
        nb.flux = fluxes(nr);
        nb.role = neighRole;
        nb.name = rxn_name(model, nr);
        neighbors{end + 1} = nb; %#ok<AGROW>
    end

    grp.metabolite = model.mets{m};
    grp.name = met_label(model, m);
    grp.role = role;
    grp.magnitude = abs(netF);
    grp.neighbors = neighbors;
    groups{end + 1} = grp; %#ok<AGROW>
end

out.groups = groups;
out.neighbor_order = model.rxns(allNeighbors);
end


function s = rxn_name(model, rxnIdx)
% Matches walkFluxes.m's getRxnName_: '' whenever rxnNames is absent or the
% entry itself is empty -- no fallback to the reaction id.
s = '';
if isfield(model, 'rxnNames') && rxnIdx <= numel(model.rxnNames)
    s = char(model.rxnNames{rxnIdx});
end
end


function s = met_label(model, metIdx)
% Matches walkFluxes.m's getMetLabel_: falls back to the metabolite id when
% metNames is absent or the entry itself is empty (unlike rxn_name above).
if isfield(model, 'metNames') && ~isempty(model.metNames{metIdx})
    s = model.metNames{metIdx};
else
    s = model.mets{metIdx};
end
end
