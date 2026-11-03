"""Shared helpers for the Layer-2 native-promotion kit.

Design goals:
- Honest by construction. Every app harness ALWAYS emits an evidence record,
  either a real verdict (EXPOSED / RESISTANT) or INCONCLUSIVE with the exact
  reason. Nothing is ever faked to a PASS.
- Resumable. The orchestrator records per-app status; a re-run skips apps that
  already completed and retries the rest.
- Self-contained. Each app brings up its own containers via docker compose and
  tears them down afterwards, so apps do not interfere with each other.

This module is stdlib + a few pip packages (see requirements.txt). It is written
to run on a host that has Docker (compose v2) available; it is NOT expected to run
inside a constrained sandbox without Docker.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #
EXPOSED = "EXPOSED"
RESISTANT = "RESISTANT"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class Evidence:
    app_id: str
    system: str
    expected_verdict: str
    verdict: str = INCONCLUSIVE
    tier: str = "native"
    version: str = ""
    decisive_surface: str = ""
    steps: list = field(default_factory=list)
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def step(self, name, detail=""):
        self.steps.append({"t": _now(), "step": name, "detail": str(detail)[:400]})

    def write(self, path):
        self.finished_at = _now()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
        # also a sha256 next to it, so the capture is tamper-evident
        with open(path + ".sha256", "w", encoding="utf-8") as fh:
            fh.write(hashlib.sha256(json.dumps(asdict(self), sort_keys=True)
                                    .encode()).hexdigest() + "\n")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextlib.contextmanager
def guarded(ev: Evidence, out_path: str):
    """Run a harness body; whatever happens, write an evidence record.
    An exception becomes INCONCLUSIVE + the error, never a silent pass."""
    ev.started_at = _now()
    try:
        yield ev
    except Exception as e:  # noqa: BLE001  (we want to record *any* failure)
        ev.verdict = INCONCLUSIVE
        # Surface Docker/DB stderr so an INCONCLUSIVE says *why*, not just the exit code.
        detail = f"{type(e).__name__}: {e}"
        for attr in ("stderr", "stdout"):
            v = getattr(e, attr, None)
            if v:
                detail += f"\n--- {attr} ---\n" + (v if isinstance(v, str) else v.decode("utf-8", "replace"))[-1500:]
        ev.verdict = INCONCLUSIVE
        ev.error = detail
        ev.step("exception", detail[:400])
    finally:
        ev.write(out_path)


# --------------------------------------------------------------------------- #
# Docker compose lifecycle
# --------------------------------------------------------------------------- #
def have_docker() -> bool:
    try:
        subprocess.run(["docker", "version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "compose", "version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def compose(app_dir, *args, timeout=1800, check=True):
    cmd = ["docker", "compose", "-f", os.path.join(app_dir, "compose.yaml")] + list(args)
    return subprocess.run(cmd, cwd=app_dir, timeout=timeout, check=check,
                          text=True, capture_output=True)


@contextlib.contextmanager
def stack(app_dir, ev: Evidence, up_timeout=1800):
    """Bring the compose stack up, yield, always tear it down (and clean volumes)."""
    ev.step("compose up")
    compose(app_dir, "up", "-d", timeout=up_timeout)
    try:
        yield
    finally:
        ev.step("compose down")
        with contextlib.suppress(Exception):
            compose(app_dir, "down", "-v", timeout=600, check=False)


# --------------------------------------------------------------------------- #
# Readiness waiters
# --------------------------------------------------------------------------- #
def wait_tcp(host, port, timeout=300, ev=None):
    end = time.time() + timeout
    while time.time() < end:
        with contextlib.suppress(OSError):
            with socket.create_connection((host, port), timeout=3):
                if ev:
                    ev.step("tcp ready", f"{host}:{port}")
                return True
        time.sleep(3)
    raise TimeoutError(f"port {host}:{port} not ready in {timeout}s")


def wait_http(url, timeout=600, ok=range(200, 500), ev=None):
    end = time.time() + timeout
    last = ""
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status in ok:
                    if ev:
                        ev.step("http ready", f"{url} -> {r.status}")
                    return r.status
        except urllib.error.HTTPError as e:
            if e.code in ok:
                if ev:
                    ev.step("http ready", f"{url} -> {e.code}")
                return e.code
            last = f"{e.code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(4)
    raise TimeoutError(f"{url} not ready in {timeout}s (last={last})")


# --------------------------------------------------------------------------- #
# Database connectors (lazy imports so a missing driver only affects its apps)
# --------------------------------------------------------------------------- #
def pg(dsn=None, **kw):
    import psycopg2
    return psycopg2.connect(dsn, **kw) if dsn else psycopg2.connect(**kw)


def mysql(**kw):
    import mysql.connector
    return mysql.connector.connect(**kw)


def mongo(uri):
    import pymongo
    return pymongo.MongoClient(uri)


def sql_exec(conn, sql, params=None, fetch=False):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall() if fetch else None
    conn.commit()
    cur.close()
    return rows


# --------------------------------------------------------------------------- #
# Schema-aware seed insert: fill every NOT NULL / no-default column the caller
# did not set, so raw-SQL seeding does not whack-a-mole one column per re-run.
# Explicit foreign keys and business values are passed in `values`; discovered
# scalar columns get a type-appropriate placeholder (enums get their first label).
# --------------------------------------------------------------------------- #
def _enum_first_label(conn, udt):
    r = sql_exec(conn, "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t "
                 "ON t.oid=e.enumtypid WHERE t.typname=%s ORDER BY e.enumsortorder "
                 "LIMIT 1", (udt,), fetch=True)
    return r[0][0] if r else None


def insert(conn, table, values, returning="id", schema="public"):
    cols = sql_exec(conn, """
        SELECT column_name, data_type, udt_name, is_nullable, column_default, is_identity
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
        (schema, table), fetch=True)
    vals = dict(values)
    for name, dtype, udt, is_nullable, default, is_identity in cols:
        if name in vals or is_nullable == "YES" or default is not None or is_identity == "YES":
            continue
        d = (dtype or "").lower()
        if d in ("character varying", "text", "character", "citext", "name"):
            vals[name] = ("apf_" + name)[:40]
        elif d == "uuid":
            vals[name] = "__RAW__gen_random_uuid()"
        elif d in ("timestamp without time zone", "timestamp with time zone", "date"):
            vals[name] = "__RAW__now()"
        elif d == "boolean":
            vals[name] = False
        elif d in ("integer", "bigint", "smallint", "numeric", "double precision", "real"):
            vals[name] = 0
        elif d in ("json", "jsonb"):
            vals[name] = "{}"
        elif d == "user-defined":
            vals[name] = _enum_first_label(conn, udt) or ""
        else:
            vals[name] = ("apf_" + name)[:40]
    names, ph, params = [], [], []
    for c, v in vals.items():
        names.append(f'"{c}"')
        if isinstance(v, str) and v.startswith("__RAW__"):
            ph.append(v[len("__RAW__"):])
        else:
            ph.append("%s"); params.append(v)
    q = f'INSERT INTO {schema}."{table}" (' + ", ".join(names) + ") VALUES (" + ", ".join(ph) + ")"
    if returning:
        q += f' RETURNING "{returning}"'
    rows = sql_exec(conn, q, tuple(params), fetch=bool(returning))
    return rows[0][0] if returning and rows else None
