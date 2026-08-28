"""Python side of the task-checking scenario.

``check_tasks`` returns a :class:`~raven_toolbox.tasks.TaskResult` per task, of
which ``passed`` is the counterpart of RAVEN's ``taskReport.ok`` --- both
already account for SHOULD FAIL.

``TaskResult.feasible`` is deliberately not emitted. RAVEN's report has no
matching field, so the only way to put one in the MATLAB result would be to
derive it from ``ok`` and ``shouldFail`` --- which is the same boolean identity
the Python side would be checked against, and would therefore assert nothing.
``should_fail`` is emitted instead: it comes straight from the parsed task on
both sides, so a difference in ``passed`` alone localises to the LP, and a
difference in both localises to the task list.

Task order is the file's, and is not sorted.

The solver is named by the scenario rather than inherited from the machine, so
that both sides are demonstrably solving with the same one --- see scenario.yml.
"""

import cobra

from raven_toolbox.io import read_yaml_model
from raven_toolbox.tasks import check_tasks, parse_task_list


def run(ctx):
    inputs = ctx["inputs"]
    # Set before the model is read: a cobra model takes its solver from the
    # configuration at construction time.
    cobra.Configuration().solver = str(inputs["python_solver"])
    model = read_yaml_model(inputs["model"])
    model.solver = str(inputs["python_solver"])
    tasks = parse_task_list(inputs["tasks"])
    results = check_tasks(model, tasks)

    records = [
        {
            "id": str(task.id),
            "description": str(task.description or ""),
            "should_fail": bool(task.should_fail),
            "passed": bool(result.passed),
        }
        for task, result in zip(tasks, results)
    ]

    return {
        "n_tasks": len(records),
        "n_passed": sum(1 for r in records if r["passed"]),
        "n_should_fail": sum(1 for r in records if r["should_fail"]),
        "tasks": records,
    }
