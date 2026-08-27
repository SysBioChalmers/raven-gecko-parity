"""Python side of the task-list parsing scenario.

``parse_task_list`` returns a list of :class:`~raven_toolbox.tasks.Task`, where
the bound-carrying fields are ``(name, lb, ub)`` triples. RAVEN returns a struct
array with the two bounds in parallel numeric fields (``inputs`` / ``LBin`` /
``UBin``). The shape below is the common denominator: a list of records per
field, which both sides can produce without either one's storage showing
through.

Nothing is sorted. Task order, and the order of entries within a task, are what
the parser produced from a sequence of rows; sorting them would hide a
disagreement about which row belongs to which task.
"""

from raven_toolbox.tasks import parse_task_list


def run(ctx):
    tasks = parse_task_list(ctx["inputs"]["task_file"])
    return {
        "n_tasks": len(tasks),
        "tasks": [_task_record(task) for task in tasks],
    }


def _task_record(task):
    return {
        "id": str(task.id),
        "description": str(task.description or ""),
        "should_fail": bool(task.should_fail),
        "print_fluxes": bool(task.print_fluxes),
        "comments": str(task.comments or ""),
        # Every key always present, so a task that happens to have no equations
        # reads as an empty list rather than as a structural difference.
        "inputs": _bounded(task.inputs, "metabolite"),
        "outputs": _bounded(task.outputs, "metabolite"),
        "equations": _bounded(task.equations, "equation"),
        "changed": _bounded(task.changed, "reaction"),
    }


def _bounded(triples, name_key):
    return [
        {name_key: str(name), "lb": float(lb), "ub": float(ub)}
        for name, lb, ub in triples
    ]
