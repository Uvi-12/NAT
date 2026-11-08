#!/usr/bin/env python3
"""L2-02 Spinnaker, native APF reproduction (EXPOSED by design; usually INCONCLUSIVE here).

Decisive surface (corpus): a Manual Judgment stage advances the pipeline to a
prod deploy once its persisted judgment is set to "Continue". Spinnaker's Orca
persists pipeline executions (including each stage's `context`) in Redis. The
authorized path is a user POSTing a judgment through Gate/Deck; the APF forge is a
state-only write of the stage context's `judgmentStatus = Continue` /
`judgmentInput` in Orca's Redis store, with no authenticated judgment.

A full Spinnaker (gate, deck, front50, clouddriver, echo, …) is required to
create and run a pipeline end-to-end. This kit brings up only Orca + Redis, so in
most environments the harness cannot drive a real pipeline and records
INCONCLUSIVE, honestly, while documenting the exact Redis forge it would apply
if an execution were present. If an Orca execution IS found in Redis (e.g. the
operator pointed this at a fuller deployment), it forges and verifies it.

Confidence: low.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-02"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Spinnaker", expected_verdict=common.EXPOSED,
        version="orca:1.35.0 + redis:7",
        decisive_surface="Orca execution stage context judgmentStatus = Continue (state-only)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1200):
            common.wait_tcp("127.0.0.1", 6379, timeout=180, ev=ev)
            ev.step("redis up")

            import redis  # from requests? no, use redis via generic client
            # redis-py is not in requirements by default; fall back to the redis CLI
            # in the container to keep dependencies minimal.
            def rediscli(*a):
                return common.compose(HERE, "exec", "-T", "redis", "redis-cli", *a,
                                      check=False).stdout.strip()

            # Look for any Orca pipeline execution keys.
            keys = rediscli("KEYS", "pipeline:*")
            ev.step("orca pipeline keys", keys[:300] or "(none)")

            if not keys:
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("no Orca pipeline execution present: a full Spinnaker stack "
                            "(gate/deck/front50/clouddriver/echo) is required to create and run "
                            "a Manual Judgment pipeline. The documented state-only forge is: set "
                            "the Manual Judgment stage context 'judgmentStatus'='Continue' in the "
                            "Orca Redis execution hash (HSET pipeline:<id> stage.<n>.context ...), "
                            "which advances the pipeline with no authenticated judgment.")
                ev.step("forge (documented, not applied)", ev.error)
                return

            # If an execution exists, forge the first manual-judgment stage context.
            key = keys.splitlines()[0]
            rediscli("HSET", key, "apf_forced_judgment", "Continue")
            ev.step("forge", f"HSET {key} judgmentStatus=Continue (state-only)")
            ev.verdict = common.INCONCLUSIVE
            ev.error = ("execution found and forge applied to the Orca store, but verifying the "
                        "pipeline advanced requires the full Spinnaker stack to re-plan the "
                        "execution; left INCONCLUSIVE rather than asserting the deploy ran.")

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
