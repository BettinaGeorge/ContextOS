# Keyword-Search Baseline: Question Set (T001)

Questions are about the **creator-dashboard** repo, which is what the owner's
"CreatorOS" workspace in the dev database was ingested from (1,764 artifacts).
Each question maps to one file, so the expected artifact is that file's GitHub
URL. The set was first written for ContextOS itself, then switched because only
CreatorOS was ingested; the baseline measures search quality, not the repo.

URL base: `https://github.com/BettinaGeorge/creator-dashboard/blob/HEAD/`

| # | Question | Expected artifact (path after URL base) |
|---|---|---|
| Q1 | How are hook ideas generated with the AI model? | `backend/services/ai_service.py` |
| Q2 | How does the ingestion layer support both an Instagram export and the Graph API? | `backend/integrations/base_client.py` |
| Q3 | How does the app load reels from the Instagram data export? | `backend/integrations/instagram_export_client.py` |
| Q4 | How are reels loaded into the database and duplicates skipped? | `backend/services/ingestion_service.py` |
| Q5 | How is performance by content category calculated? | `backend/services/analytics_service.py` |
| Q6 | How is a reel's viral performance predicted before posting? | `backend/ml/predictor.py` |
| Q7 | How was the prediction model trained? | `backend/ml/train_model.py` |
| Q8 | How are reels tagged with a niche? | `backend/models/reel_tag.py` |
| Q9 | How does the backend connect to the database? | `backend/core/database.py` |
| Q10 | How does the frontend fetch data from the API? | `src/lib/api.ts` |
| Q11 | Why is the backend split into controllers, services and repositories? | `docs/adr/001-layered-backend-architecture.md` |
| Q12 | Why was a strategy pattern used for ingestion? | `docs/adr/002-ingestion-strategy-pattern.md` |
| Q13 | Why does the reel tags table have no foreign key? | `docs/adr/003-reel-tags-no-foreign-key.md` |
| Q14 | Why did the project pivot away from machine-learning prediction? | `docs/adr/004-ml-exploration-and-pivot.md` |
| Q15 | Which AI model does the content studio use and why? | `docs/adr/005-ai-model-selection.md` |
| Q16 | How are the tests set up without a live Postgres database? | `docs/adr/007-testing-approach.md` |

If a question reports MISSED on the baseline run, check that the file was part
of the ingest (for example, very large files may be absent); replace that
question rather than counting it against search.

## Recorded run (T003, owner)

_Not run yet. Record the commit hash and per-question results here before any
retrieval change (T031, T032)._
