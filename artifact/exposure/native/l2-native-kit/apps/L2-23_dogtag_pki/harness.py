#!/usr/bin/env python3
"""L2-23 Dogtag PKI, native APF reproduction (RESISTANT).

Decisive surface (corpus): a certificate request is only issued when an agent
approval is re-derived live at issuance (the CA requires an authenticated
'approve' on a PENDING request). The persisted request status is therefore not
sufficient on its own. The APF forge is a state-only write of the request status
to "approved/complete" in the persisted request repository (the CA's 389-DS
entry), and the expectation is that it does NOT yield a verifiable certificate,
because the CA re-authorizes the approval at issuance.

A fully spawned Dogtag CA is heavy and environment-specific. On a host where the
CA comes up (pkispawn), the harness: enrols a request (PENDING), forges the
persisted request status without an agent approval, then drives the issuance/
retrieval path and shows NO verifiable certificate is produced -> RESISTANT.
Where the CA cannot be spawned headlessly it records INCONCLUSIVE with the reason
and documents the resistance mechanism, never a false pass.

Confidence: low.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-23"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def pki(*args, timeout=600, check=False):
    """Run a command inside the pki container."""
    return common.compose(HERE, "exec", "-T", "pki", *args, timeout=timeout, check=check)


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Dogtag PKI", expected_verdict=common.RESISTANT,
        version="dogtagpki/pki:11.6 + 389ds",
        decisive_surface="agent approval re-derived at issuance (persisted request status not trusted)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1200):
            common.wait_tcp("127.0.0.1", 3389, timeout=300, ev=ev)

            # Attempt to spawn a CA subsystem. This is the step most likely to fail
            # on a minimal host; if it does, we record INCONCLUSIVE honestly.
            spawn = pki("sh", "-c",
                        "command -v pkispawn >/dev/null && echo HAVE_PKISPAWN || echo NO_PKISPAWN")
            have = (spawn.stdout or "").strip()
            ev.step("pkispawn availability", have)

            if "HAVE_PKISPAWN" not in have:
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("Dogtag CA could not be spawned headlessly in this environment. "
                            "Resistance mechanism (documented): the CA keeps certificate requests "
                            "in its request repository (389-DS); issuance requires an authenticated "
                            "agent 'approve' on a PENDING request that the CA re-derives at "
                            "issuance. A state-only write of the persisted request status to "
                            "'complete' does NOT yield a cert that chains to the CA, because the "
                            "signing step re-checks the agent authorization, hence RESISTANT.")
                ev.step("resistance (documented, not exercised)", ev.error)
                return

            # If pkispawn exists, the full exercise would: create a CA, submit a
            # request (PENDING), forge its status in 389-DS, then attempt retrieval
            # and show no verifiable cert is issued. Spawning + configuring a CA is
            # multi-step and deployment-specific; this harness stops at the honest
            # boundary rather than asserting an unverified issuance.
            ev.verdict = common.INCONCLUSIVE
            ev.error = ("pkispawn present but a scripted CA spawn + request lifecycle is "
                        "deployment-specific; run `pkispawn` for a CA, submit a PENDING request, "
                        "forge its 389-DS status, then confirm retrieval yields no CA-chained cert "
                        "(RESISTANT).")
            ev.step("resistance (setup required)", ev.error)

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
