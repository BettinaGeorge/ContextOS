# Phase 0 Research: Trace a Spec/Doc to Code

Most technology choices are already resolved in `docs/decisions/ADR-001-weekend-mvp-stack.md` — this document only covers implementation-level unknowns not settled at that granularity. No `NEEDS CLARIFICATION` markers remain in `plan.md`'s Technical Context after this research.

## 1. Where does job polling run, given the $10 budget?

**Decision**: An in-process asyncio background task (`backend/src/core/job_worker.py`) started on FastAPI startup, polling the `jobs` table on a short interval (e.g. every 5s) — not a separate worker process.

**Rationale**: Render's free tier covers one web service; a dedicated background-worker instance is a paid Render resource. Running the poller inside the same process as the API keeps this at $0, consistent with the budget constraint in ADR-001. This is an acceptable trade at this scale (single repo + single Notion source ingestion, not a high-throughput queue).

**Alternatives considered**: A separate Render worker service — rejected, would break the $10/non-recurring budget the moment it's provisioned. Celery/RQ with hosted Redis — already rejected in ADR-001 for the same budget reason; doesn't change here.

**Consequence to flag**: an in-process poller means ingestion jobs stop if the free-tier instance spins down from inactivity. Acceptable for Phase 1 (a user triggers ingestion and is expected to be actively using the product at that time); revisit if this causes real problems.

## 2. How does the backend verify a user's identity?

**Decision**: Supabase issues a JWT to the frontend on sign-in; the frontend sends it as a Bearer token; FastAPI verifies it using the Supabase project's JWT secret (PyJWT, HS256) in a dependency (`core/auth.py`) that extracts the user id (`sub` claim) for use in all workspace-scoped queries.

**Rationale**: Standard Supabase Auth integration pattern; no separate session store needed on the backend.

**Alternatives considered**: Backend-managed sessions/cookies — rejected, redundant with what Supabase Auth already provides and adds state to keep in sync.

## 3. Code chunking granularity (deferred in spec.md Assumptions)

**Decision**: Function/class-boundary chunking for source files where a lightweight parser is feasible in the time available (Python: `ast` module, stdlib, no new dependency; TypeScript/JavaScript: a simple regex/heuristic boundary split, not a full parser). Fall back to fixed-size flat-text chunking for any file type without a boundary strategy. Commits, PRs, issues, and Notion pages are chunked by natural structural boundaries (PR description as one chunk, each Notion block or block-group as a chunk) rather than fixed-size splitting.

**Rationale**: The handoff (§13) and PRD raised this to a real Phase 1 target once the timeline extended past a single weekend — naive flat-text chunking would materially hurt retrieval quality on the one workflow this phase exists to prove. Using Python's built-in `ast` module avoids a new dependency for the language most likely to appear in a test repo.

**Alternatives considered**: Full AST-aware multi-language parsing (e.g. tree-sitter) — rejected as more than this phase needs; naive flat-text chunking for everything — rejected, undersells the core workflow now that time allows better.

## 4. Deterministic link detection between Notion and GitHub

**Decision**: Regex extraction — a GitHub PR/commit URL (`github.com/{owner}/{repo}/(pull|commit)/...`) found anywhere in a Notion page's text content creates a `document → pull_request` or `document → commit` relationship with `origin = explicit`. Symmetrically, a Notion page URL (`notion.so/...` or the workspace's custom domain) found in a PR/commit description creates the same relationship from the GitHub side. Both directions checked at ingestion time.

**Rationale**: Matches the convention defined in PRD §4; simple, auditable, no false-positive risk from fuzzy matching.

**Alternatives considered**: NLP/semantic matching to infer the link — rejected for this relationship type specifically, since an explicit URL is exactly the deterministic signal Constitution Principle II asks to prefer.

## 5. Vector index strategy

**Decision**: No special pgvector index (HNSW/IVFFlat) for Phase 1 — a plain `vector` column with sequential scan. Revisit only if query latency becomes a real problem.

**Rationale**: Data volume at this scale (one repo + one Notion source) is small enough that index tuning is premature optimization — directly against Constitution Principle V (narrowest credible scope).

**Alternatives considered**: HNSW index upfront — rejected as unnecessary complexity for the current data volume.

## 6. GitHub / Notion API clients

**Decision**: `httpx` direct calls to the GitHub REST API (simpler than pulling in PyGithub for the small surface needed: repo metadata, files, PRs, commits, issues) and the official `notion-client` Python SDK for Notion (handles pagination and rate-limit backoff already).

**Rationale**: Minimal dependencies; GitHub's authenticated rate limit (5,000 req/hr) comfortably covers single-repo ingestion; Notion's SDK removes the need to hand-roll its pagination/rate-limit handling.

**Alternatives considered**: PyGithub — rejected as an extra dependency for a small, well-known REST surface that `httpx` covers directly.
