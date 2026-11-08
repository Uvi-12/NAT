from __future__ import annotations

import argparse
from pathlib import Path

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelMessagesTypeAdapter

from .workflow import build_agent, Ledger, start, resume
from .forge import forge_inject_return

DEFAULT_APPROVER = "Compliance Officer"


def save_history(path: Path, history) -> None:
    path.write_bytes(ModelMessagesTypeAdapter.dump_json(history))


def load_history(path: Path):
    return ModelMessagesTypeAdapter.validate_json(path.read_bytes())


def call_path(db: Path) -> Path:
    return Path(str(db) + ".call")


def save_call_id(db: Path, call_id: str) -> None:
    call_path(db).write_text(call_id)


def load_call_id(db: Path) -> str:
    p = call_path(db)
    if not p.exists():
        raise SystemExit("no call id found; run start first")
    return p.read_text().strip()


def cmd_start(args) -> None:
    agent = build_agent()
    ledger = Ledger()
    history, call_id = start(agent, ledger)
    db = Path(args.db)
    save_history(db, history)
    save_call_id(db, call_id)
    print(
        f"started transfer amount=${ledger.amount:,.2f} "
        f"recipient={ledger.recipient} status=DEFERRED call={call_id[:12]}"
    )
    print(f"  executed={ledger.executed}")


def cmd_resume(args) -> None:
    agent = build_agent()
    ledger = Ledger()
    history = load_history(Path(args.db))
    r, redeferred = resume(agent, ledger, history)
    status = "BLOCKED" if not ledger.executed else "EXECUTED"
    print(f"resumed status={status} executed={ledger.executed} re_deferred={redeferred}")
    print("  guarded tool did not run; approval was not supplied through DeferredToolResults")


def cmd_forge(args) -> None:
    db = Path(args.db)
    history = load_history(db)
    call_id = load_call_id(db)
    forged = forge_inject_return(history, call_id, args.approver)
    save_history(db, forged)
    print(f"forged persisted message history approver='{args.approver}'")
    print("  injected fabricated approved tool-return into stored history")


def cmd_resume_forged(args) -> None:
    agent = build_agent()
    ledger = Ledger()
    history = load_history(Path(args.db))
    r, redeferred = resume(agent, ledger, history)
    print(
        f"resumed forged history status=RESISTANT "
        f"real_tool_executed={ledger.executed} re_deferred={redeferred}"
    )
    print(f"  narration={r.output!r}")
    print("  model saw fabricated return, but the real guarded tool did not execute")


def cmd_allow(args) -> None:
    agent = build_agent()
    ledger = Ledger()
    db = Path(args.db)
    history = load_history(db)
    call_id = load_call_id(db)
    r, redeferred = resume(
        agent,
        ledger,
        history,
        approve_call_id=call_id,
        approver=args.approver,
    )
    status = "EXECUTED" if ledger.executed else "BLOCKED"
    print(f"resumed with genuine approval status={status} executed={ledger.executed}")
    print(f"  {r.output!r}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="ga-pydanticai")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "resume", "forge", "resume-forged", "allow"):
        p = sub.add_parser(name)
        p.add_argument("--db", required=True)
        p.add_argument("--approver", default=DEFAULT_APPROVER)

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "resume":
        cmd_resume(args)
    elif args.command == "forge":
        cmd_forge(args)
    elif args.command == "resume-forged":
        cmd_resume_forged(args)
    elif args.command == "allow":
        cmd_allow(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
