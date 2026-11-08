# APF native reproduction, Galaxy (publish/visibility gate)

Native-tier (N1) reproduction against the **real Galaxy model runtime**
(`galaxy-data` 26.1.2, the shipped `galaxy.model` package and its schema), driving
Galaxy's own ORM rather than a reconstruction. It promotes the Layer-2 Galaxy row
from contract-level (N2) to native.

- **System / version:** Galaxy `galaxy-data` **26.1.2** (the shipped data/model layer).
- **Decisive surface:** `History.published` (`model/__init__.py:3656`. The
  published-histories read predicate in `managers/sharable.py:106,158`).
- **Mechanism:** PFV, a public-flag value held in a writable relational row.

## What it shows (captured in `evidence/evidence.json`)

Using Galaxy's real model layer and the schema built by
`galaxy.model.mapping.init(...)`:

1. A `History` is created through the real ORM, owned by a user, `published=False`
   (the model's own default). **Control:** the published-histories read predicate
   (`History.published == True`) does not return it, not world-visible. The
   authorised path to flip this is the owner's publish action through the sharable
   manager.
2. **Forge (state-only):** one direct write, `UPDATE history SET published = 1` , 
   with **no** publish action, by **no** owner, and **no** manager call.
3. **Resume/read-back:** the real ORM reloads the row and reports
   `History.published == True`. The same shipped read predicate now returns the
   history as world-visible.

Verdict: **EXPOSED**, the visibility decision trusts the persisted `published`
column, which carries no provenance of who published or how. A state-writer who can
write that column makes a private record world-visible without the publish action
and without ownership.

## Scope of this run (honest tier)

This run executes the vendor's **shipped model/ORM and schema** and the documented
read predicate against the state mutation. It is a model/ORM-tier native run: it
does not start the Galaxy web controller (the `galaxy.managers`/HTTP layer is not in
the `galaxy-data` distribution), so the controller wrapper over the same predicate
is cited, not executed. The decisive surface, the `published` column and the read
predicate that trusts it, is exercised natively.

## How to reproduce

```
python3 -m venv .venv && . .venv/bin/activate
pip install galaxy-data
python3 run_galaxy.py      # writes evidence/evidence.json (+ .sha256)
```
