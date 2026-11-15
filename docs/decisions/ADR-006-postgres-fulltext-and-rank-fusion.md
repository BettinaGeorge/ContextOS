# ADR-006: PostgreSQL full-text search with OR queries, merged by reciprocal rank fusion

Status: Accepted (2026-11-15; validated in `specs/003-reliability-hardening/validation.md`).

## Context

Keyword retrieval is a case-insensitive substring match of the whole question against title and content, so a natural-language question almost never matches. Keyword and vector results are concatenated, with keyword hits first, so a strong vector match can be pushed out by weak keyword matches. The constraints are $0 and no new service.

## Decision

- Add a stored generated `tsvector` column on artifacts (`english` configuration, title plus the first 200,000 characters of content) with a GIN index.
- Tokenise the question in Python to letters and digits, lower-case, de-duplicate, cap at 12 tokens, and join with ` | ` into `to_tsquery`. Order by `ts_rank`. No tokens means no query.
- Merge keyword and vector lists by reciprocal rank fusion (`1 / (60 + rank)` summed per artifact) in `RetrievalService`.

## Consequences

- Partial matches are returned and ranked by how many terms hit; special characters cannot reach the query parser.
- Code identifiers are split by the English configuration (for example `get_by_id`); this is verified in the quickstart and can be revisited with a second `simple`-configuration column if it hurts recall.
- Adds storage for the generated column and index.
- Requires PostgreSQL 12 or later.
- Stemming is English-only, which matches the current repository and Notion content.

## Alternatives considered

- **`websearch_to_tsquery` or `plainto_tsquery`**: AND all terms, so one missing word loses the match.
- **`pg_trgm` similarity**: needs an extension and ranks poorly on long text.
- **BM25 extension or external search service**: new dependency, violates the constitution's constraints.
- **Weighted score mixing**: keyword rank and cosine distance are not comparable.
- **Fusion in SQL**: more complex and harder to test than a small pure function.
