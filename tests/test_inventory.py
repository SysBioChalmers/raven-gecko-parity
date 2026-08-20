"""What counts as public API on each side."""

from __future__ import annotations

import ast

from parity.inventory import _literal_all, build_inventory, scan_matlab, scan_python


def test_matlab_scan_lists_public_functions_only(fake_pair):
    names = {fn.name for fn in scan_matlab(fake_pair.matlab)}
    assert names == {"addRxns", "predictLocalization", "exportModel"}


def test_matlab_scan_records_paths(fake_pair):
    paths = {fn.name: fn.path for fn in scan_matlab(fake_pair.matlab)}
    assert paths["addRxns"] == "core/addRxns.m"


def test_python_scan_reads_dunder_all(fake_pair):
    exports = {e.qualname for e in scan_python(fake_pair.python)}
    assert exports == {"fakepy.add_reactions", "fakepy.manipulation.export_model"}


def test_python_scan_ignores_modules_without_dunder_all(fake_pair):
    names = {e.name for e in scan_python(fake_pair.python)}
    assert "helper" not in names


def test_re_exports_collapse_to_the_shortest_qualname(fake_pair):
    """`add_reactions` is exported twice; it is one function, so it gets one entry."""
    exports = {e.name: e for e in scan_python(fake_pair.python)}
    assert exports["add_reactions"].qualname == "fakepy.add_reactions"
    assert exports["add_reactions"].aliases == ("fakepy.manipulation.add_reactions",)


def test_definition_is_traced_through_the_re_export_chain(fake_pair):
    """The top-level export re-exports from a sub-package, which re-exports from a module."""
    exports = {e.name: e for e in scan_python(fake_pair.python)}
    assert exports["add_reactions"].defined_in == "src/fakepy/manipulation/add.py"


def test_source_map_lets_a_changed_file_reach_its_exports(fake_pair):
    by_source = build_inventory(fake_pair).python_by_source()
    reached = {e.name for e in by_source["src/fakepy/manipulation/export.py"]}
    assert reached == {"export_model"}


def test_last_dunder_all_wins_like_it_does_at_import_time():
    tree = ast.parse("__all__ = ['early']\n__all__ = ['late']\n")
    assert _literal_all(tree) == ["late"]


def test_dunder_all_augmentation_is_followed():
    tree = ast.parse("__all__ = ['a']\n__all__ += ['b']\n")
    assert _literal_all(tree) == ["a", "b"]
