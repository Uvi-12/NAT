"""Command-line interface for the Semantic Kernel process-state integrity demo.

Commands
--------
demo     Run the full sequence: start, control resume, forge, resume.
start    Persist the initial unapproved state.
status   Report the persisted approval and execution state.
forge    Record an approval in the persisted state.
resume   Restore the state and report the settlement outcome.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import tempfile

from .forge import inject_approval
from .store import open_store, read_state
from .workflow import START_AMOUNT, resume, start_transfer

DEFAULT_DB = os.path.join(tempfile.gettempdir(), "ga_sk_state.json")
DEFAULT_APPROVER = "Rahul S. (Senior Compliance Officer) [14:32:01]"


def cmd_start(args) -> None:
    store = open_store(args.db)
    asyncio.run(start_transfer(store, amount=START_AMOUNT, recipient=args.recipient))
    print(f"started transfer amount=${START_AMOUNT:,.2f} recipient={args.recipient} (awaiting approval)")


def cmd_status(args) -> None:
    state = read_state(args.db)
    if state is None:
        print("no persisted state found"); return
    print(
        f"transfer_approved={state.get('transfer_approved')} "
        f"executed={state.get('executed')} approver={state.get('approver')!r}"
    )


def cmd_forge(args) -> None:
    store = open_store(args.db)
    if not store.exists():
        print("no persisted state found"); return
    inject_approval(store, approver=args.approver)
    print(f"injected approval approver={args.approver!r}")


def cmd_resume(args) -> None:
    store = open_store(args.db)
    if not store.exists():
        print("no persisted state found"); return
    result = asyncio.run(resume(store))
    print(
        f"resumed status={result['status']} approved={result['approved']} "
        f"executed={result['executed']} approver={result['approver']!r}"
    )
    print(f"  {result['message']}")


def cmd_demo(args) -> None:
    if os.path.exists(args.db):
        os.remove(args.db)
    print("== start ==");            cmd_start(args)
    print("== resume (control) =="); cmd_resume(args)
    print("== forge ==");            cmd_forge(args)
    print("== resume ==");           cmd_resume(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ga-sk", description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB, help="serialized state file path")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="persist the initial unapproved state")
    p.add_argument("--recipient", default="ACME-CORP")
    p.set_defaults(func=cmd_start)

    sub.add_parser("status", help="report persisted state").set_defaults(func=cmd_status)

    p = sub.add_parser("forge", help="record an approval in the persisted state")
    p.add_argument("--approver", default=DEFAULT_APPROVER)
    p.set_defaults(func=cmd_forge)

    p = sub.add_parser("resume", help="restore state and settle")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("demo", help="run the full sequence")
    p.add_argument("--recipient", default="ACME-CORP")
    p.add_argument("--approver", default=DEFAULT_APPROVER)
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
