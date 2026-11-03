# Native APF reproduction, TUF (python-tuf). Resistance is native: the trusted
# decision (which artifacts are authorized) is bound to a signature a state-writer
# cannot forge. Uses the real tuf.api.metadata + securesystemslib signer.
import json
from tuf.api.metadata import Metadata, Targets, TargetFile
from securesystemslib.signer import CryptoSigner
from securesystemslib.exceptions import UnverifiedSignatureError

def line(s): print(s)

# the approval authority holds a signing key the state-writer does NOT have
signer = CryptoSigner.generate_ed25519()
pub = signer.public_key

# authorized decision: targets metadata listing the one approved artifact
targets = Targets(version=1)
targets.targets["approved-release-1.0.tgz"] = TargetFile.from_data(
    "approved-release-1.0.tgz", b"the genuinely approved artifact bytes")
md = Metadata(targets)
md.sign(signer)                       # real signature by the authority
persisted = md.to_bytes()             # <-- the persisted metadata ("approval state")
line("=== python-tuf native APF (signed targets metadata) ===")
line("persisted signed targets metadata: %d bytes, %d target(s)" %
     (len(persisted), len(targets.targets)))

def verify(blob, label):
    m = Metadata.from_bytes(blob)
    try:
        pub.verify_signature(m.signatures[pub.keyid], m.signed_bytes)
        line("  [%s] signature verifies -> TRUSTED (%d targets)" % (label, len(m.signed.targets)))
        return True
    except (UnverifiedSignatureError, KeyError) as e:
        line("  [%s] signature INVALID -> REJECTED (%s)" % (label, type(e).__name__))
        return False

line("")
line("[control] verify the genuine persisted metadata:")
ok_genuine = verify(persisted, "genuine")

line("")
line("[forge] state-writer edits the PERSISTED metadata (no signing key): inject a")
line("        malicious target 'backdoor.tgz' and re-serialize, keeping the old signature.")
doc = json.loads(persisted)
doc["signed"]["targets"]["backdoor.tgz"] = {
    "length": 10, "hashes": {"sha256": "00"*32}}       # attacker-authored target
# (attacker cannot re-sign: no key) -> leave signatures untouched
tampered = json.dumps(doc).encode()

line("[resume] verify the tampered persisted metadata against the trusted key:")
ok_forged = verify(tampered, "forged")

line("")
line("[forge-2] attacker tries to re-sign with their OWN key (not trusted):")
ev_signer = CryptoSigner.generate_ed25519()
m2 = Metadata.from_bytes(tampered); 
try:
    m2.sign(ev_signer)
    attacker_ok = False
    try:
        pub.verify_signature(m2.signatures.get(pub.keyid), m2.signed_bytes); attacker_ok=True
    except Exception: attacker_ok=False
    line("  attacker re-signed with own key; trusted-key verification: %s" %
         ("ACCEPTED(!!)" if attacker_ok else "REJECTED"))
except Exception as e:
    line("  attacker re-sign rejected: %s" % type(e).__name__)

line("")
resistant = ok_genuine and (not ok_forged)
line("VERDICT: %s" % ("RESISTANT, the authorized set of artifacts is bound to a signature "
     "the state-writer cannot produce; a state-only edit of the persisted metadata is "
     "rejected at verification, and re-signing needs a key the writer does not hold."
     if resistant else "inconclusive"))
import sys; sys.exit(0 if resistant else 2)
