# Native APF reproduction, in-toto. The supply-chain step attestation (a "link")
# and the policy ("layout") are signature-bound; a state-writer who edits the
# persisted attestation cannot forge the functionary's signature. Real in_toto libs.
import json
from in_toto.models.link import Link
from in_toto.models.metadata import Metablock
from securesystemslib.signer import CryptoSigner
from securesystemslib.exceptions import UnverifiedSignatureError

def line(s): print(s)

# functionary holds a key the state-writer does not have
F = CryptoSigner.generate_ed25519(); Fpub = F.public_key
FKEY = {**Fpub.to_dict(), 'keyid': Fpub.keyid}  # legacy key dict in_toto expects

# genuine step attestation: "build" produced the approved artifact
link = Link(name="build",
            materials={"src/app.py": {"sha256": "aa"*32}},
            products={"dist/app.whl": {"sha256": "bb"*32}},
            command=["python","-m","build"], byproducts={}, environment={})
mb = Metablock(signed=link)
mb.create_signature(F)                 # real functionary signature
persisted = json.dumps(mb.to_dict()).encode()
line("=== in-toto native APF (signed step attestation / link) ===")
line("persisted signed link: %d bytes, product dist/app.whl=bb...bb" % len(persisted))

def verify(blob, label):
    m = Metablock.from_dict(json.loads(blob))
    try:
        m.verify_signature(FKEY)
        prod = list(m.signed.products.items())
        line("  [%s] functionary signature verifies -> ACCEPTED (product %s=%s)" %
             (label, prod[0][0], prod[0][1]['sha256'][:6]))
        return True
    except (UnverifiedSignatureError, Exception) as e:
        line("  [%s] signature INVALID -> REJECTED (%s)" % (label, type(e).__name__))
        return False

line("")
line("[control] verify the genuine persisted link:")
ok_genuine = verify(persisted, "genuine")

line("")
line("[forge] state-writer edits the PERSISTED link (no key): swap the attested")
line("        product hash to a malicious artifact, keep the old signature.")
doc = json.loads(persisted)
doc["signed"]["products"]["dist/app.whl"]["sha256"] = "de"*32   # attacker-chosen
tampered = json.dumps(doc).encode()
line("[resume] verify the tampered persisted link against the functionary key:")
ok_forged = verify(tampered, "forged")

line("")
resistant = ok_genuine and (not ok_forged)
line("VERDICT: %s" % ("RESISTANT, the step attestation is bound to the functionary's "
    "signature; a state-only edit of the persisted link (swapping the approved artifact) "
    "is rejected at verification, and the writer cannot re-sign without the key."
    if resistant else "inconclusive"))
import sys; sys.exit(0 if resistant else 2)
