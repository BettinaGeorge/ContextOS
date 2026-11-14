# Migration Rehearsal (T013)

Revision `a7d3c91e5b20`, rehearsed on 2026-11-14 on a copy of the owner's local dev
database (`createdb -T contextos_dev contextos_dev_copy`). The real database was not touched.

The copy's recorded revision was feature 002's `0af7f199cc2c`, which does not exist on this
branch, so it was reset to `4500f22c8686` with SQL on the copy only. The migration does not
touch the tables 002 changes (connectors).

| Count | Before | After |
|---|---|---|
| Artifacts | 2,060 | 214 |
| Identities with more than one row | 585 | 0 |
| Relationships | 68 | 57 |
| Connectors with 2+ active jobs | 0 | 0 |

**Reading the result**

- All 585 duplicate identities collapsed to one row each.
- Most of the 1,846 removed artifacts are legacy GitHub source files, which the migration
  deletes by design (their blob-SHA identity cannot be mapped to the new path identity).
  GitHub files, and therefore every file-based answer, are empty until the next ingest.
- 11 relationships were removed as duplicates or because they pointed at deleted source files.
- Migration ran without error.

**Consequence for the real database:** applying the migration there means re-ingesting each
GitHub connector afterwards, which re-embeds every file (embedding quota).

## Re-ingest on the copy (owner)

Run with `--skip-embeddings` (the free embedding tier needs hours for a whole repo), CreatorOS
workspace, commit b68b742:

- before: 588 artifacts, 1 relationship (the 24 left after the migration plus ones from earlier attempts)
- ingested github: 587 pieces; ingested notion: 1 piece
- after: 588 artifacts, 1 relationship; no duplicate identities
- New relationships: 0 (expected: only one Notion page, so few explicit links to resolve)

Second text-only run (same command): 588 artifacts and 1 relationship before and after, so a repeat
run adds no duplicates on real data.

Not shown by these runs: the "second run embeds zero texts" proof, because nothing was embedded.
That behaviour is covered by the integration tests in `test_idempotent_ingestion.py`. A full run
with embeddings is still needed before applying the migration to the real database.
