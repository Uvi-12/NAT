"""Command-line interface for the BeeAI resistance demonstration.

Commands: deny | forge | allow | surface | demo
"""
from __future__ import annotations

import argparse
import asyncio
import json

from .forge import persisted_approval_surface
from .workflow import settle

DEFAULT_APPROVER = "Compliance Officer"


async def _deny(tool, tool_input) -> bool:
    return False


async def _allow(tool, tool_input) -> bool:
    return True


def _print_result(result: dict) -> None:
    print(f"status={result['status']} executed={result['executed']}")
    print(f"  {result['message']}")


def cmd_deny(_args) -> None:
    result = asyncio.run(settle(_deny))
    _print_result(result)


def cmd_allow(_args) -> None:
    result = asyncio.run(settle(_allow, approver=DEFAULT_APPROVER))
    _print_result(result)


def cmd_forge(_args) -> None:
    surface = persisted_approval_surface()
    print("attempted persistence-layer forge")
    print(
        "status=RESISTANT "
        f"executed=False persisted_approval_artifact={surface['has_persisted_approval']}"
    )
    print(f"  decision_source={surface['decision_source']}")
    print("  result=no persisted approval state was available to modify")


def cmd_surface(_args) -> None:
    print(json.dumps(persisted_approval_surface(), indent=2))


def cmd_demo(_args) -> None:
    print("== live deny ==")
    cmd_deny(_args)
    print("== attempted persistence-layer forge ==")
    cmd_forge(_args)
    print("== live allow ==")
    cmd_allow(_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ga-beeai",
        description="BeeAI resistant control for approval-provenance testing.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("deny", help="run gate with live deny decision").set_defaults(func=cmd_deny)
    sub.add_parser("forge", help="attempt persistence-layer approval forge").set_defaults(func=cmd_forge)
    sub.add_parser("allow", help="run gate with live allow decision").set_defaults(func=cmd_allow)
    sub.add_parser("surface", help="report persisted approval surface").set_defaults(func=cmd_surface)
    sub.add_parser("demo", help="run combined resistance demonstration").set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
