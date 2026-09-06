function results = compare_fluxes_smallyeast(ctx)
% MATLAB side of the compareFluxes/compare_fluxes scenario.
%
% Calls compareFluxes itself -- it returns a struct, so unlike walkFluxes or
% the removed followChanged there is nothing to reimplement here.

model = readYAMLmodel(ctx.inputs.model);

fluxes1 = build_dense(model, ctx.inputs.fluxes_1);
fluxes2 = build_dense(model, ctx.inputs.fluxes_2);
cutoff = ctx.inputs.cutoff;

unfiltered = compareFluxes(model, fluxes1, fluxes2, 'cutoff', cutoff, 'verbose', false);
filtered = compareFluxes(model, fluxes1, fluxes2, 'cutoff', cutoff, ...
    'metaboliteList', cellstr(ctx.inputs.metabolite_list), 'verbose', false);

results.unfiltered = checkpoint(unfiltered);
results.filtered = checkpoint(filtered);
end


function fluxes = build_dense(model, sparse_inputs)
fluxes = zeros(numel(model.rxns), 1);
fnames = fieldnames(sparse_inputs);
for i = 1:numel(fnames)
    idx = find(strcmp(model.rxns, fnames{i}));
    fluxes(idx) = sparse_inputs.(fnames{i});
end
end


function out = checkpoint(result)
% changed is a cell array rather than a struct array: jsonencode renders a
% one-element struct array as a bare object, where the Python side always
% produces a list.

changed = {};
for i = 1:numel(result.changed.rxn)
    row.reaction = result.changed.rxn{i};
    row.flux1 = result.changed.flux1(i);
    row.flux2 = result.changed.flux2(i);
    row.abs_delta = result.changed.absDelta(i);
    row.rel_change = result.changed.relChange(i);
    row.type = result.changed.type{i};
    changed{end+1} = row; %#ok<AGROW>
end

% In compareFluxes' own order: the descending sort by absDelta is part of what
% this scenario checks. The three id lists come out in model order and carry no
% ordering claim, so they are sorted before comparing.
out.changed = changed;
out.turned_on = sort_ids(result.turnedOn);
out.turned_off = sort_ids(result.turnedOff);
out.flipped = sort_ids(result.flipped);
end


function ids = sort_ids(ids)
if isempty(ids)
    ids = {};
else
    ids = sort(ids(:))';
end
end
