function results = gapfill_connect_smallyeast(ctx)
% MATLAB side of the connectivity gap-filling scenario.
%
% fillGaps returns newConnected / cannotConnect / addedRxns / newModel as four
% parallel outputs where the Python side returns one result object; the three
% that describe the outcome line up directly.
%
% The uptake bounds are opened by assigning into model.ub rather than through
% setParam, so that the fixture preparation cannot itself become the thing
% under test.

inputs = ctx.inputs;

% The solver is named by the scenario rather than inherited: RAVEN's default
% glpk cannot solve a MILP at all, and a run that silently used a different
% solver from the Python side would be comparing solvers rather than toolboxes.
% The preference is global and the nightly runs several scenarios in one MATLAB
% session, so whatever was set is put back on the way out.
previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(inputs.matlab_solver));

results.single = checkpoint(inputs, as_cellstr(inputs.single_removed));
results.double = checkpoint(inputs, as_cellstr(inputs.double_removed));

end


function out = checkpoint(inputs, removed)
draft = prepared(inputs, removed);
template = prepared(inputs, {});
% fillGaps refuses a reference model sharing the draft's id, and both come from
% the same file here.
template.id = char(inputs.template_id);

before = draft.rxns(:);

[newConnected, cannotConnect, addedRxns, newModel] = fillGaps(draft, {template}, ...
    'allowNetProduction', logical(inputs.allow_net_production), ...
    'useModelConstraints', logical(inputs.use_model_constraints), ...
    'supressWarnings', true);

out.n_reactions_before = numel(before);
out.n_added = numel(addedRxns);
out.added_reactions = sort_cellstr(addedRxns);
out.n_newly_connected = numel(newConnected);
out.newly_connected = sort_cellstr(newConnected);
out.n_cannot_connect = numel(cannotConnect);
out.cannot_connect = sort_cellstr(cannotConnect);
out.filled_reactions = sort_cellstr(newModel.rxns);
end


function model = prepared(inputs, removed)
model = readYAMLmodel(inputs.model);

opened = as_cellstr(inputs.opened_reactions);
for k = 1:numel(opened)
    i = find(strcmp(model.rxns, opened{k}), 1);
    if isempty(i)
        error('gapfill_connect:noReaction', 'no reaction %s to open', opened{k});
    end
    model.ub(i) = double(inputs.opened_upper_bound);
end

if ~isempty(removed)
    model = removeReactions(model, removed);
end
end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end


function out = as_cellstr(value)
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
