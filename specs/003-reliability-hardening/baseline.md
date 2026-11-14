# Keyword-Search Baseline: Question Set (T001)

Draft written with the owner's picks. Each question maps to one file in the
ContextOS repo, so the expected artifact is that file's GitHub URL.

**Assumption to confirm:** the GitHub repo ingested into the local database is
ContextOS itself. If it is a different repo, this set must be redone.

URL base: `https://github.com/BettinaGeorge/ContextOS/blob/HEAD/`


found through the GitHub connector, not Notion.

| # | Question | Expected artifact (path after URL base) |
|---|---|---|
| Q1 | How does the system make sure every citation was actually retrieved? | `backend/src/services/answer_svc.py` |
| Q2 | How are keyword and vector results combined before answering? | `backend/src/services/retrieval_svc.py` |
| Q3 | What happens when there is not enough evidence to answer? | `backend/src/services/answer_svc.py` |
| Q4 | How are retrieved documents kept separate from the model's instructions? | `backend/src/llm/groq_client.py` |
| Q5 | How is code split into pieces before embedding? | `backend/src/services/chunking.py` |
| Q6 | How are files, pull requests and commits pulled from GitHub? | `backend/src/connectors/github_connector.py` |
| Q7 | How are Notion pages fetched? | `backend/src/connectors/notion_connector.py` |
| Q8 | How are ingestion jobs picked up, and what happens when one fails? | `backend/src/core/job_worker.py` |
| Q9 | How are connector tokens protected? | `backend/src/repositories/connector_repository.py` |
| Q10 | How is data scoped to a workspace? | `backend/src/repositories/artifact_repository.py` |
| Q11 | How does sign-in work? | `backend/src/core/auth.py` |
| Q12 | How are docs linked to pull requests and commits? | `backend/src/services/relationship_svc.py` |
| Q13 | Why was Groq chosen as the LLM provider? | `docs/decisions/ADR-002-groq-llm-provider.md` |
| Q14 | What is explicitly out of scope for Phase 1? | `docs/prd.md` |
| Q15 | What comes after Phase 1 and why? | `docs/roadmap.md` |
| Q16 | Why was this stack and hosting chosen? | `docs/decisions/ADR-001-weekend-mvp-stack.md` |

Note: the question set is 16, above the "about ten" in the spec; the script
reports each question separately, so extra questions only make the baseline
more informative.

## Recorded run (T003, owner)

_Not run yet. Record the commit hash and per-question results here before any
retrieval change (T031, T032)._
