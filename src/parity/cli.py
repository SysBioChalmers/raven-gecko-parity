"""The ``parity`` command line.

    parity check              validate the ledgers against both repos
    parity sync               add ledger rows for anything newly public
    parity report             render the Markdown parity document
    parity mirror             what does my current change mean for the other side?
    parity scenarios          list the cross-implementation scenarios
    parity run                run one scenario against one implementation
    parity compare            diff two scenario result files
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from parity.config import Config, ConfigError, Pair, load_config
from parity.inventory import build_inventory
from parity.ledger import LedgerError, load_ledger, save_ledger
from parity.scenarios import (
    ScenarioError,
    Tolerance,
    compare_results,
    list_scenarios,
    load_scenario,
    run_matlab,
    run_python,
    write_result,
)


def _pairs(config: Config, requested: str | None) -> list[Pair]:
    if requested:
        return [config.pair(requested)]
    return [config.pairs[name] for name in sorted(config.pairs)]


def _scenario_root(config: Config) -> Path:
    return config.root / "scenarios"


def cmd_check(args: argparse.Namespace, config: Config) -> int:
    from parity.check import run_check
    from parity.report import render_check

    from parity.mirror import describe

    failed = False
    for index, pair in enumerate(_pairs(config, args.pair)):
        if index:
            print()
        result = run_check(pair)
        revisions = (describe(pair.matlab.path), describe(pair.python.path))
        print(render_check(result, strict=args.strict, revisions=revisions))
        failed = failed or not result.ok(strict=args.strict)
    return 1 if failed else 0


def cmd_sync(args: argparse.Namespace, config: Config) -> int:
    from parity.seed import sync_ledger

    for pair in _pairs(config, args.pair):
        ledger, added, summary = sync_ledger(pair)
        pairing = (
            f"{summary.exact} exact + {summary.expanded} expanded name pairings, "
            f"{summary.matlab_unmatched} MATLAB and {summary.python_unmatched} Python left unpaired"
        )
        if args.dry_run:
            print(f"{pair.name}: {added} row(s) would be added to {pair.ledger}")
            print(f"{'':<{len(pair.name) + 2}}{pairing}")
            continue
        save_ledger(ledger, pair.ledger)
        print(f"{pair.name}: {added} row(s) added, {len(ledger.entries)} total -> {pair.ledger}")
        print(f"{'':<{len(pair.name) + 2}}{pairing}")
    return 0


def cmd_report(args: argparse.Namespace, config: Config) -> int:
    from parity.check import run_check
    from parity.report import render

    for pair in _pairs(config, args.pair):
        inventory = build_inventory(pair)
        ledger = load_ledger(pair.ledger)
        result = run_check(pair, inventory=inventory, ledger=ledger)
        text = render(ledger, result)

        if args.output:
            target = Path(args.output)
            # A path without a .md suffix is a directory to write <pair>.md into --- which is
            # also the only thing that can work when rendering more than one pair.
            if target.suffix != ".md":
                target.mkdir(parents=True, exist_ok=True)
                target = target / f"{pair.name}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"{pair.name}: wrote {target}")
        else:
            print(text)
    return 0


def cmd_mirror(args: argparse.Namespace, config: Config) -> int:
    from parity import mirror

    pair, side = _resolve_repo(config, args)
    result = mirror.analyse(pair, side, since=args.since)
    print(mirror.render(result, pair, brief=args.brief))
    if args.fail_on_parity and result.needs_attention:
        return 1
    return 0


def _resolve_repo(config: Config, args: argparse.Namespace) -> tuple[Pair, str]:
    """Work out which side of which pair the user means.

    With no flags, the current working directory decides --- so the git hook needs no
    arguments at all.
    """
    if args.pair and args.side:
        return config.pair(args.pair), args.side

    here = Path(args.repo).resolve() if args.repo else Path.cwd().resolve()
    for pair in config.pairs.values():
        for side in ("matlab", "python"):
            root = pair.side(side).path
            if here == root or root in here.parents:
                return pair, side
    raise ConfigError(
        f"{here} is not inside any repo configured in parity.toml --- "
        "pass --pair and --side, or run from inside one of the four repos"
    )


def cmd_scenarios(args: argparse.Namespace, config: Config) -> int:
    scenarios = list_scenarios(_scenario_root(config), args.pair)
    if not scenarios:
        print("no scenarios defined")
        return 0
    for scenario in scenarios:
        covers = ", ".join(scenario.entries) or "--"
        print(f"{scenario.id:<32} [{scenario.pair}]  {scenario.description}")
        print(f"{'':<32} covers: {covers}")
    return 0


def cmd_run(args: argparse.Namespace, config: Config) -> int:
    directory = _scenario_root(config) / args.scenario
    if not directory.is_dir():
        print(f"no such scenario: {args.scenario}", file=sys.stderr)
        return 2

    scenario = load_scenario(directory)
    pair = config.pair(scenario.pair) if scenario.pair else None
    if args.impl == "python":
        document = run_python(scenario, config.root, pair)
    else:
        document = run_matlab(scenario, config.root, pair, matlab=args.matlab)

    target = Path(args.output) if args.output else config.root / "results" / args.impl / f"{scenario.id}.json"
    write_result(document, target)
    print(f"{scenario.id} [{args.impl}] -> {target}")
    return 0


def cmd_compare(args: argparse.Namespace, config: Config) -> int:
    left = json.loads(Path(args.left).read_text(encoding="utf-8"))
    right = json.loads(Path(args.right).read_text(encoding="utf-8"))

    tolerance = Tolerance(rel=args.rel, abs=args.abs)
    if args.scenario:
        tolerance = load_scenario(_scenario_root(config) / args.scenario).tolerance

    differences = compare_results(left, right, tolerance)
    label = f"{left.get('implementation', '?')} vs {right.get('implementation', '?')}"
    print(f"scenario: {left.get('scenario', '?')}  ({label})")
    print(f"tolerance: rel={tolerance.rel:g} abs={tolerance.abs:g}")

    if not differences:
        print("result:   MATCH")
        return 0

    print(f"\n{len(differences)} difference(s):")
    for difference in differences[: args.limit]:
        print(difference.format())
    if len(differences) > args.limit:
        print(f"  ... and {len(differences) - args.limit} more")
    print("\nresult:   DIFFER")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parity", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "-c",
        "--config",
        help="path to parity.toml (default: $PARITY_CONFIG, else the nearest one above the cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate the ledgers against both repos")
    check.add_argument("--pair", help="only this pair (default: all)")
    check.add_argument("--strict", action="store_true", help="also fail on warnings and unreviewed rows")
    check.set_defaults(func=cmd_check)

    sync = sub.add_parser("sync", help="add ledger rows for anything newly public")
    sync.add_argument("--pair", help="only this pair (default: all)")
    sync.add_argument("-n", "--dry-run", action="store_true", help="report what would be added, write nothing")
    sync.set_defaults(func=cmd_sync)

    report = sub.add_parser("report", help="render the Markdown parity document")
    report.add_argument("--pair", help="only this pair (default: all)")
    report.add_argument("-o", "--output", help="write to this file or directory instead of stdout")
    report.set_defaults(func=cmd_report)

    mirror_cmd = sub.add_parser("mirror", help="what does my current change mean for the other side?")
    mirror_cmd.add_argument("--pair", help="pair name (default: inferred from the cwd)")
    mirror_cmd.add_argument("--side", choices=("matlab", "python"), help="side (default: inferred from the cwd)")
    mirror_cmd.add_argument("--repo", help="look at this checkout instead of the cwd")
    mirror_cmd.add_argument("--since", help="a rev or range, e.g. 'HEAD~1' or 'develop..HEAD' (default: uncommitted work)")
    mirror_cmd.add_argument("--brief", action="store_true", help="hook-sized output")
    mirror_cmd.add_argument(
        "--fail-on-parity",
        action="store_true",
        help="exit non-zero when a function declared at parity was touched",
    )
    mirror_cmd.set_defaults(func=cmd_mirror)

    scenarios = sub.add_parser("scenarios", help="list the cross-implementation scenarios")
    scenarios.add_argument("--pair", help="only this pair")
    scenarios.set_defaults(func=cmd_scenarios)

    run = sub.add_parser("run", help="run one scenario against one implementation")
    run.add_argument("scenario")
    run.add_argument("--impl", choices=("python", "matlab"), required=True)
    run.add_argument("-o", "--output", help="result JSON path (default: results/<impl>/<scenario>.json)")
    run.add_argument("--matlab", default="matlab", help="MATLAB executable (default: matlab)")
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare", help="diff two scenario result files")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--scenario", help="take the tolerance from this scenario's declaration")
    compare.add_argument("--rel", type=float, default=1e-6, help="relative tolerance (default: 1e-6)")
    compare.add_argument("--abs", type=float, default=1e-9, help="absolute tolerance (default: 1e-9)")
    compare.add_argument("--limit", type=int, default=25, help="max differences to print (default: 25)")
    compare.set_defaults(func=cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # PARITY_CONFIG lets `parity mirror` work from inside any of the four repos without
    # flags --- which is what the git hooks rely on.
    configured = args.config or os.environ.get("PARITY_CONFIG")
    try:
        config = load_config(Path(configured) if configured else None)
        return args.func(args, config)
    except (ConfigError, LedgerError, ScenarioError, FileNotFoundError) as exc:
        print(f"parity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
