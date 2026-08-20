function results = elemental_balance_smallyeast(ctx)
% MATLAB side of the elemental-balance scenario.
%
% Must return exactly the shape run.py returns --- same field names, same ordering rules,
% same conventions --- because `parity compare` diffs the two structurally. Where the two
% toolboxes disagree, that is the finding; where the *harness* disagrees, that is a bug
% here.
%
% Two conventions worth stating, because they are the easy way to get a false difference:
%   * sorting --- reaction lists are sorted by id on both sides, not left in model order;
%   * imbalance sign --- right-hand side minus left-hand side, matching what
%     raven_toolbox reports.

DETAIL_LIMIT = 25;
zeroTolerance = ctx.inputs.zero_tolerance;

model = readYAMLmodel(ctx.inputs.model);
balance = getElementalBalance(model);

status = balance.balanceStatus(:);
results.n_reactions = numel(status);

% Fixed keys, always present, mirroring run.py. RAVEN's -2 ("could not be balanced due to
% an error") has no Python counterpart; it is reported separately rather than folded into
% "unknown" so that a real occurrence surfaces as a difference.
results.verdicts = struct( ...
    'balanced',   sum(status == 1), ...
    'unbalanced', sum(status == 0), ...
    'unknown',    sum(status == -1), ...
    'error',      sum(status == -2));

unbalancedIdx = find(status == 0);
[unbalancedIds, order] = sort(model.rxns(unbalancedIdx));
unbalancedIdx = unbalancedIdx(order);

results.n_unbalanced = numel(unbalancedIds);
results.unbalanced_reactions = unbalancedIds(:)';

% Element-level detail for a bounded, deterministic slice of the unbalanced reactions.
% Built as a cell array of structs rather than a struct array: jsonencode turns a 1x1
% struct array into a bare object instead of a one-element array, which would not match
% the Python side.
nDetail = min(DETAIL_LIMIT, numel(unbalancedIds));
detail = cell(1, nDetail);

elementNames = balance.elements.abbrevs(:)';
imbalance = balance.rightComp - balance.leftComp;

for k = 1:nDetail
    row = imbalance(unbalancedIdx(k), :);
    nonzero = find(abs(row) > zeroTolerance);

    elements = cell(1, numel(nonzero));
    for j = 1:numel(nonzero)
        elements{j} = struct( ...
            'element', elementNames{nonzero(j)}, ...
            'amount',  double(row(nonzero(j))));
    end

    % Element order must match the Python side, which sorts by element symbol.
    if ~isempty(elements)
        symbols = cellfun(@(e) e.element, elements, 'UniformOutput', false);
        [~, elementOrder] = sort(symbols);
        elements = elements(elementOrder);
    end

    detail{k} = struct( ...
        'reaction', unbalancedIds{k}, ...
        'elements', {elements});
end

results.imbalance_detail = detail;

end
