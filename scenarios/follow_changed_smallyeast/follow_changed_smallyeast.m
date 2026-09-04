function results = follow_changed_smallyeast(ctx)
% MATLAB side of the followChanged/follow_changed scenario.
%
% Reimplements followChanged.m's selection logic (its lines building
% ineither/fluxIndexes) rather than calling followChanged itself, which only
% prints and returns nothing. Same approach walk_fluxes_smallyeast and
% duplicate_reactions_smallyeast take for their own real, print-only or
% blocking source functions.

model = readYAMLmodel(ctx.inputs.model);

fluxesA = build_dense(model, ctx.inputs.fluxes_a);
fluxesB = build_dense(model, ctx.inputs.fluxes_b);

results.filtered = checkpoint(model, fluxesA, fluxesB, ctx.inputs.cutoff_flux, ...
    ctx.inputs.cutoff_diff, ctx.inputs.cutoff_change, ctx.inputs.metabolite_list);
end


function fluxes = build_dense(model, sparse_inputs)
fluxes = zeros(numel(model.rxns), 1);
fnames = fieldnames(sparse_inputs);
for i = 1:numel(fnames)
    idx = find(strcmp(model.rxns, fnames{i}));
    fluxes(idx) = sparse_inputs.(fnames{i});
end
end


function out = checkpoint(model, fluxesA, fluxesB, cutOffFlux, cutOffDiff, cutOffChange, metaboliteList)
missing = {};
reactionIndexes = [];
for i = 1:numel(metaboliteList)
    metaboliteIndex = find(strcmpi(metaboliteList{i}, model.metNames));
    if ~isempty(metaboliteIndex)
        [~, b] = find(model.S(metaboliteIndex, :));
        reactionIndexes = [reactionIndexes; b(:)]; %#ok<AGROW>
    else
        missing{end+1} = metaboliteList{i}; %#ok<AGROW>
    end
end
reactionIndexes = unique(reactionIndexes);

in1 = find(abs(fluxesA(reactionIndexes)) >= cutOffFlux)';
in2 = find(abs(fluxesB(reactionIndexes)) >= cutOffFlux)';
ineither = reactionIndexes(unique([in1 in2]));

ineither = ineither(abs(fluxesA(ineither) - fluxesB(ineither)) >= cutOffDiff);

nonZeroFluxes = ineither(fluxesA(ineither) ~= 0);
quota = 1 + cutOffChange / 100;
larger = nonZeroFluxes((fluxesB(nonZeroFluxes) ./ fluxesA(nonZeroFluxes)) >= quota)';
smaller = nonZeroFluxes((fluxesB(nonZeroFluxes) ./ fluxesA(nonZeroFluxes)) < (1 / quota))';
fluxIndexes = [larger smaller];

zeroFluxes = ineither(fluxesA(ineither) == 0);
fluxIndexes = unique([fluxIndexes zeroFluxes(abs(fluxesB(zeroFluxes)) >= cutOffFlux)']);

changed = {};
for i = 1:numel(fluxIndexes)
    idx = fluxIndexes(i);
    row.reaction = model.rxns{idx};
    row.name = model.rxnNames{idx};
    row.flux = fluxesA(idx);
    row.reference_flux = fluxesB(idx);
    row.difference = fluxesA(idx) - fluxesB(idx);
    changed{end+1} = row; %#ok<AGROW>
end

[~, order] = sort(cellfun(@(r) r.reaction, changed, 'UniformOutput', false));
out.changed = changed(order);
out.missing_metabolites = sort(missing);
end
