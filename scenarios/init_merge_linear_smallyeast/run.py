"""Python side of the ftINIT linear-merge stage.

``merge_linear`` and RAVEN's ``mergeLinear`` return the same four things --- the
reduced model, the original reaction ids, a group id per original reaction, and
a reversed flag per original reaction --- so the two line up directly.

Three checkpoints: the merge with nothing protected, the merge with the
boundary reactions protected, and ``group_rxn_scores`` on top of the second.

Shape rules, per docs/scenarios.md: sort everything, always emit every key,
lists of records rather than objects keyed by model identifiers.
"""

from raven_toolbox.init import group_rxn_scores, merge_linear
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    path = inputs["model"]
    protected = [str(rxn) for rxn in inputs["protected_reactions"]]

    merge_all = merge_linear(read_yaml_model(path))
    merge_protected = merge_linear(read_yaml_model(path), protected)

    return {
        "merge_all": _merge_checkpoint(*merge_all),
        "merge_protected": _merge_checkpoint(*merge_protected),
        "scores": _score_checkpoint(inputs, *merge_protected),
    }


def _merge_checkpoint(reduced, orig_ids, group_ids, reversed_flags):
    grouped = dict(zip(orig_ids, group_ids, strict=True))

    members = {}
    for rxn_id, group in grouped.items():
        if group:
            members.setdefault(group, []).append(rxn_id)

    # Sorted member lists, ordered by their first member: a canonical form for
    # the partition that does not depend on how either side numbered its
    # groups. The raw integers are deliberately *not* compared --- see
    # scenario.yml.
    partition = sorted((sorted(ids) for ids in members.values()), key=lambda ids: ids[0])
    index_of = {rxn_id: n for n, ids in enumerate(partition, start=1) for rxn_id in ids}

    return {
        "n_reactions_before": len(orig_ids),
        "n_reactions_after": len(reduced.reactions),
        "n_groups": len(members),
        "n_merged": sum(1 for group in group_ids if group),
        "n_reversed": sum(1 for flag in reversed_flags if flag),
        "reactions": sorted(rxn.id for rxn in reduced.reactions),
        "group_index": [
            {"reaction": rxn_id, "group_index": index_of.get(rxn_id, 0)}
            for rxn_id in sorted(orig_ids)
        ],
        "groups": [{"members": ids} for ids in partition],
        "reversed_reactions": sorted(
            rxn_id for rxn_id, flag in zip(orig_ids, reversed_flags, strict=True) if flag
        ),
        # The merge has to preserve the chemistry, not just the counts: a
        # contraction of the right chains combined the wrong way would agree on
        # every number above.
        "bounds": [
            {
                "reaction": rxn.id,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
            }
            for rxn in sorted(reduced.reactions, key=lambda r: r.id)
        ],
        "stoichiometry": _stoichiometry(reduced),
    }


def _score_checkpoint(inputs, reduced, orig_ids, group_ids, _reversed):
    declared = {str(k): float(v) for k, v in dict(inputs["scores"]).items()}
    # Every original reaction needs a score: the ones not named in the
    # declaration are a genuine zero, which both sides lift to 0.01.
    orig_scores = {rxn_id: declared.get(rxn_id, 0.0) for rxn_id in orig_ids}

    scores = group_rxn_scores(
        reduced,
        orig_scores,
        list(orig_ids),
        list(group_ids),
        [str(rxn) for rxn in inputs["scores_to_zero"]],
    )

    return {
        "n_reactions": len(scores),
        "scores": [
            {"reaction": rxn_id, "score": float(scores[rxn_id])}
            for rxn_id in sorted(scores)
        ],
    }


def _stoichiometry(model):
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coeff)}
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["metabolite"]))
    return entries
