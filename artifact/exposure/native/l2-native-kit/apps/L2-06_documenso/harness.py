#!/usr/bin/env python3
"""L2-06 Documenso, native APF reproduction (EXPOSED).

Decisive surface (corpus): a document/envelope is treated as fully signed when its
persisted `status == 'COMPLETED'`; Documenso trusts that stored enum and does not
re-derive the PAdES signature at the point it serves the completed document.

Forge: a state-only write of that persisted status (PENDING -> COMPLETED) in
PostgreSQL, with no signing ceremony. We seed a minimal document row via the real
Prisma schema, capture the blocked control (status != COMPLETED), forge the status,
and verify the app's own database view now reports the document completed.

Documenso renamed the aggregate from `Document` to `Envelope` across versions; the
harness tries the `Envelope` table first and falls back to `Document`. Targets
documenso v1.11.1 (adjust the image tag to match your deployment).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-06"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="documenso",
          user="documenso", password="documenso")


def table_for(conn):
    """Return the aggregate table name present in this Documenso version."""
    for t in ('Envelope', 'Document'):
        rows = common.sql_exec(
            conn, "SELECT to_regclass(%s)", (f'public."{t}"',), fetch=True)
        if rows and rows[0][0] is not None:
            return t
    raise RuntimeError("neither Envelope nor Document table found (schema mismatch)")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Documenso", expected_verdict=common.EXPOSED,
        version="documenso v1.11.1",
        decisive_surface="Document/Envelope.status == 'COMPLETED'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            # the app runs prisma migrate on boot; wait for its HTTP surface
            common.wait_http("http://127.0.0.1:3000", timeout=1800, ev=ev)

            conn = common.pg(**PG)
            tbl = table_for(conn)
            ev.step("aggregate table", tbl)

            # --- seed: a user + document-data + a PENDING document ---
            # Schema-aware seed: we set only the business fields; common.insert
            # fills every other NOT NULL / no-default column (DocumentData.id cuid,
            # Document.source/visibility enums, timestamps, ...) from the live schema.
            uid = common.insert(conn, "User",
                {"name": "APF User", "email": "apf-user@example.com"}, returning="id")
            ddid = common.insert(conn, "DocumentData",
                {"type": "BYTES", "data": "APF", "initialData": "APF"}, returning="id")
            doc_id = common.insert(conn, tbl,
                {"title": "APF Agreement", "status": "PENDING",
                 "userId": uid, "documentDataId": ddid}, returning="id")
            ev.step("seeded document", f"id={doc_id} status=PENDING")

            # --- control: not completed ---
            status0 = common.sql_exec(
                conn, f'SELECT status FROM public."{tbl}" WHERE id=%s',
                (doc_id,), fetch=True)[0][0]
            ev.step("control status", status0)
            if str(status0) == "COMPLETED":
                raise RuntimeError("control precondition failed: already COMPLETED")

            # --- forge: state-only write of the trusted status ---
            common.sql_exec(
                conn, f'UPDATE public."{tbl}" SET status=%s, "updatedAt"=now() WHERE id=%s',
                ("COMPLETED", doc_id))
            ev.step("forge", f'UPDATE "{tbl}" SET status=COMPLETED WHERE id={doc_id}')

            # --- verify: the app's own stored view now reports completed ---
            status1 = common.sql_exec(
                conn, f'SELECT status FROM public."{tbl}" WHERE id=%s',
                (doc_id,), fetch=True)[0][0]
            ev.step("verify status", status1)

            if str(status0) != "COMPLETED" and str(status1) == "COMPLETED":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write set the trusted COMPLETED status "
                                   "with no signing ceremony; Documenso serves it as signed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected status: control={status0} after_forge={status1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
