function results = gapfill_topology_smallyeast(ctx)
% MATLAB side of the topological gap-analysis scenario.
%
% gapFillTopological returns reachableMets as a logical vector over model.mets
% and candidateRxns as a cell array aligned with blockedMets; run.py returns a
% set of ids and a dict. Both are flattened here to sorted lists of ids and
% records, so neither side's storage shows through into the comparison.

modelPath = ctx.inputs.model;

draft = readYAMLmodel(modelPath);
universal = readYAMLmodel(modelPath);

removed = as_cellstr(ctx.inputs.removed_reactions);
% removeUnusedMets left at its default (false): metabolites that fall out of
% use stay in the model, matching remove_orphans=False on the other side.
% Dropping them would change the target set.
draft = removeReactions(draft, removed);

seeds = as_cellstr(ctx.inputs.seeds);
targets = as_cellstr(ctx.inputs.targets);

% verbose off: the summary goes to stdout and has no counterpart in the result
% document.
result = gapFillTopological(draft, universal, ...
    'seeds', seeds, 'targets', targets, 'verbose', false);

reachable = draft.mets(logical(result.reachableMets(:)));
blocked = result.blockedMets(:);

results.n_removed = numel(removed);
results.n_reachable = numel(reachable);
results.reachable_metabolites = sort_cellstr(reachable);

% Sorted here, and the candidate lists reordered to match, because
% gapFillTopological returns blockedMets in model order and run.py sorts.
[blockedSorted, order] = sort(blocked);
results.n_blocked = numel(blockedSorted);
results.blocked_metabolites = row(blockedSorted);

candidates = result.candidateRxns(:);
records = cell(1, numel(blockedSorted));
for k = 1:numel(blockedSorted)
    i = order(k);
    if i <= numel(candidates)
        rxns = candidates{i};
    else
        rxns = {};
    end
    % Every blocked metabolite present even when nothing produces it: an
    % absent key would read as a structural difference rather than as an
    % empty candidate list.
    records{k} = struct( ...
        'metabolite', blockedSorted{k}, ...
        'reactions', {sort_cellstr(rxns)});
end
results.candidate_reactions = records;

results.pruning_fraction = double(result.pruningFraction);

end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end


function out = row(values)
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
end


function out = as_cellstr(value)
% jsondecode returns a cell array of char for a JSON array of strings, but a
% bare char for a single string and an empty array for an empty list.
if ischar(value)
    out = {value};
elseif iscell(value)
    out = value(:)';
    for k = 1:numel(out)
        if isstring(out{k})
            out{k} = char(out{k});
        end
    end
else
    out = {};
end
end
