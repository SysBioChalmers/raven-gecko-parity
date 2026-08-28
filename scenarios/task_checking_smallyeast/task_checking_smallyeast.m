function results = task_checking_smallyeast(ctx)
% MATLAB side of the task-checking scenario.
%
% checkTasks returns taskReport with parallel id / description / ok fields;
% run.py returns one record per task. Both are flattened to the same list, in
% the order the task file declares, which is not sorted.
%
% shouldFail comes from the parsed task structure rather than from the report,
% mirroring run.py: `ok` already folds SHOULD FAIL in, so emitting the flag
% beside it is what separates a disagreement about the LP from a disagreement
% about the task list.

% The solver is named by the scenario rather than inherited, so that both sides
% are demonstrably solving with the same one. The preference is global and the
% nightly runs several scenarios in one MATLAB session, so whatever was set is
% put back on the way out.
previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

model = readYAMLmodel(ctx.inputs.model);

% printOutput off: the harness reads the returned struct, and checkTasks would
% otherwise print a table into the run log for every scenario execution.
[taskReport, ~, taskStructure] = checkTasks(model, ctx.inputs.tasks, 'printOutput', false);

n = numel(taskReport.ok);
records = cell(1, n);
for k = 1:n
    records{k} = struct( ...
        'id', char(taskReport.id{k}), ...
        'description', char(taskReport.description{k}), ...
        'should_fail', logical(taskStructure(k).shouldFail), ...
        'passed', logical(taskReport.ok(k)));
end

results.n_tasks = n;
results.n_passed = sum(taskReport.ok ~= 0);
results.n_should_fail = sum(arrayfun(@(t) logical(t.shouldFail), taskStructure));
% Cell array of structs, not a struct array: jsonencode turns a 1x1 struct
% array into a bare object instead of a one-element array.
results.tasks = records;

end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
