"""Comparing results across two languages, where the traps are floats and shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from parity.scenarios import (
    ScenarioError,
    Tolerance,
    _canonical,
    build_context,
    compare_results,
    compare_values,
    load_scenario,
)

TIGHT = Tolerance(rel=1e-9, abs=1e-12)


def diff_paths(left, right, tolerance=TIGHT):
    return [d.path for d in compare_values(left, right, tolerance)]


def test_identical_results_match():
    assert not diff_paths({"a": [1, 2.0], "b": "x"}, {"a": [1, 2.0], "b": "x"})


def test_last_bit_float_noise_is_tolerated():
    """The two toolboxes sum the same coefficients in a different order."""
    assert not diff_paths({"v": -8.799999999999994}, {"v": -8.799999999999997})


def test_a_real_numeric_disagreement_is_reported():
    assert diff_paths({"v": 1.0}, {"v": 1.01}) == ["results.v"]


def test_zero_tolerance_still_admits_exact_equality():
    assert not diff_paths({"v": 2.0}, {"v": 2}, Tolerance(rel=0, abs=0))


def test_a_missing_key_is_located_by_name():
    assert diff_paths({"a": 1, "b": 2}, {"a": 1}) == ["results.b"]


def test_differences_are_reported_with_a_navigable_path():
    differences = compare_values({"outer": [{"inner": 1.0}]}, {"outer": [{"inner": 2.0}]}, TIGHT)
    assert differences[0].path == "results.outer[0].inner"


def test_a_length_mismatch_is_reported_once_not_per_element():
    assert diff_paths({"xs": [1, 2, 3]}, {"xs": [1]}) == ["results.xs"]


def test_booleans_are_not_compared_as_numbers():
    """Python's True == 1 would otherwise let a flag masquerade as a count."""
    assert diff_paths({"flag": True}, {"flag": 1}) == ["results.flag"]


def test_results_from_different_scenarios_refuse_to_compare():
    differences = compare_results(
        {"scenario": "a", "results": {}}, {"scenario": "b", "results": {}}, TIGHT
    )
    assert differences[0].path == "scenario"


def test_non_finite_floats_survive_json():
    assert _canonical({"a": float("nan"), "b": float("inf"), "c": float("-inf")}) == {
        "a": "NaN",
        "b": "Infinity",
        "c": "-Infinity",
    }


def test_canonical_form_sorts_keys():
    assert list(_canonical({"z": 1, "a": 2})) == ["a", "z"]


def write_scenario(tmp_path: Path, body: str) -> Path:
    directory = tmp_path / "demo"
    directory.mkdir()
    (directory / "scenario.yml").write_text(body, encoding="utf-8")
    return directory


def test_the_matlab_entry_is_named_after_the_scenario(tmp_path):
    """`run.m` would shadow a MATLAB builtin."""
    scenario = load_scenario(write_scenario(tmp_path, "id: demo\npair: fake\n"))
    assert scenario.matlab_entry.name == "demo.m"
    assert scenario.python_entry.name == "run.py"


def test_repo_placeholders_are_substituted(tmp_path, fake_pair):
    directory = write_scenario(tmp_path, "id: demo\npair: fake\ninputs:\n  where: '{matlab_repo}/core/addRxns.m'\n")
    context = build_context(load_scenario(directory), tmp_path, fake_pair)

    assert context["inputs"]["where"].endswith("core/addRxns.m")
    assert Path(context["inputs"]["where"]).is_file(), "an existing path resolves to an absolute one"


def test_an_unknown_placeholder_is_an_error_not_a_silent_literal(tmp_path, fake_pair):
    directory = write_scenario(tmp_path, "id: demo\npair: fake\ninputs:\n  where: '{nonesuch}/x'\n")
    with pytest.raises(ScenarioError, match="nonesuch"):
        build_context(load_scenario(directory), tmp_path, fake_pair)


def test_non_path_inputs_pass_through_untouched(tmp_path, fake_pair):
    directory = write_scenario(tmp_path, "id: demo\npair: fake\ninputs:\n  seed: 42\n  mode: strict\n")
    context = build_context(load_scenario(directory), tmp_path, fake_pair)
    assert context["inputs"] == {"seed": 42, "mode": "strict"}
