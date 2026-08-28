"""Python side of the condition-prelude scenario.

apply_condition's prelude.reset_exchanges step cannot distinguish RAVEN's
directional exchange types at all --- its own docstring says so plainly:
"cobrapy doesn't distinguish RAVEN's in / out directions; we reset every
exchange reaction." Given a condition that names one specific direction
("out"), RAVEN's applyCondition resets only the reactions that direction
names (via getExchangeRxns(model, 'out')); apply_condition resets every
exchange reaction it can find (model.exchanges), whatever direction was
actually asked for.

On smallYeast that is the difference between three reactions (glcIN,
o2IN, ethIN --- RAVEN's own "in" direction) staying at their pre-condition
bounds and getting silently reset wide open, which is enough on its own to
take the model from unable to grow at all to a triple-digit growth rate.
"""

import cobra

from raven_toolbox.conditions import apply_condition
from raven_toolbox.io import read_yaml_model

cobra.Configuration().processes = 1

UNIT_EXCHANGE_REACTIONS = sorted(
    ["acOUT", "biomassOUT", "co2OUT", "ethIN", "ethOUT", "glcIN", "glyOUT", "o2IN"]
)


def run(ctx):
    inputs = ctx["inputs"]
    cobra.Configuration().solver = str(inputs["python_solver"])

    model = read_yaml_model(inputs["model"])
    model.solver = str(inputs["python_solver"])

    apply_condition(
        model, {"prelude": {"reset_exchanges": str(inputs["reset_exchanges"])}}
    )

    bounds_after = [
        {
            "reaction": rxn_id,
            "lb": float(model.reactions.get_by_id(rxn_id).lower_bound),
            "ub": float(model.reactions.get_by_id(rxn_id).upper_bound),
        }
        for rxn_id in UNIT_EXCHANGE_REACTIONS
    ]

    growth_after = float(model.slim_optimize())

    return {
        "exchange_bounds_after": bounds_after,
        "growth_after": growth_after,
    }
