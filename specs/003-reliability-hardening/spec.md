# Feature Specification: Phase 1 Reliability Hardening

**Feature Branch**: `003-reliability-hardening`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "Phase 1 hardening: make ingestion and retrieval reliable without changing the product scope. (1) Ingestion job claiming must be safe if more than one worker runs: two workers must never run the same queued job. (2) Failed ingestion jobs must be retried a bounded number of times with backoff before being marked failed, and the final error must stay visible on the status page. (3) Re-ingesting a connector must be idempotent: running it twice produces the same artifacts, never duplicates, and unchanged artifacts (same checksum) are not re-embedded. (4) Keyword retrieval must use real Postgres full-text search with ranking instead of an ILIKE substring match on the whole question, and keyword and vector results must be merged by rank fusion instead of concatenation. (5) Retrieved content placed in the evidence block must be escaped so a document containing the closing evidence tag cannot break out of its delimiter, with an adversarial test proving it. Out of scope: new connectors, OAuth (feature 002), incremental sync, graph retrieval, any change to the citation-validation or abstention behaviour."

## Why this feature exists

Phase 1 shipped with five known reliability gaps. Each one is either written down already (ADR-001 "Consequences", a comment in the relationship-extraction code, the README "Known limitations") or visible in the code:

- Every re-ingestion inserts all artifacts again and re-embeds all of them. The `checksum` field was added "for detecting unchanged content on re-ingestion" (feature 001 data model) but nothing uses it, and the relationship step states that Phase 1 "accepts possible duplicate rows."
- The keyword half of retrieval looks for the whole question as one substring, so a natural-language question almost never matches, and the keyword and vector results are simply concatenated.
- Ingestion jobs are claimed with a read-then-update that is only safe with exactly one worker, and a failed job is never retried.
- Retrieved text is placed inside a delimited evidence section without escaping, so a document that contains the closing delimiter can end the section early. This is the exact class of attack Constitution Principle III exists to prevent.

The constitution treats reliability as a product requirement, and the roadmap puts a "Reliability pass" at Phase 3 with the instruction not to add features before it. This feature pulls the five smallest, best-understood gaps forward because they affect answer quality and cost today. It does not add product surface.

## User Scenarios & Testing *(mandatory)*

In this feature the "user" is either the person asking ContextOS questions (who is affected by answer quality and safety) or the operator running ingestion (who is affected by duplicates, cost and failures). For this project today they are the same person.

### User Story 1 - Untrusted content cannot rewrite the prompt structure (Priority: P1)

A repository file, commit message, PR description or Notion page contains text crafted to look like the end of the evidence section, a new evidence item, or a forged item attribute. When a question retrieves that artifact, the crafted text is treated as ordinary content and cannot end the evidence section, add items, or alter any item's identifying fields.

**Why this priority**: Constitution Principle III (untrusted content boundary). The prompt separation tested today only checks where content lands, not that content cannot reshape the structure around it. It is also the cheapest of the five to prove, and a public-facing weakness in an AI-safety-focused project.

**Independent Test**: Build evidence items whose content, title and source URL contain break-out strings, render the evidence section, and assert that the number of evidence items and the structure are exactly what the retrieval returned, with no content appearing outside an item.

**Acceptance Scenarios**:

1. **Given** an artifact whose content includes the closing marker of the evidence section followed by new instructions, **When** it is included in an answer request, **Then** the rendered request still contains exactly one evidence section and the injected text appears only inside that artifact's own item.
2. **Given** an artifact whose content includes a complete fake evidence item with its own identifier, **When** it is included in an answer request, **Then** the model is shown only the real items, and the fake identifier is not presented as a separate item.
3. **Given** an artifact whose title or source address contains a quote character or markup intended to end an attribute early, **When** it is rendered, **Then** the item's identifier, type, origin and address fields keep their true values.
4. **Given** an artifact whose content contains the literal citation marker text, **When** the answer is produced, **Then** citation validation still accepts only identifiers that were actually retrieved (existing behavior, unchanged).

---

### User Story 2 - Re-ingesting never duplicates or needlessly re-embeds (Priority: P1)

An operator clicks ingest again on a connector, whether to refresh content or after a failed run. The workspace ends up with the same set of artifacts and relationships as one clean ingestion of the current source, changed content is updated in place, and unchanged content is not sent to the embedding service again.

**Why this priority**: Duplicates directly degrade answers (the same passage fills several of the limited evidence slots) and re-embedding everything on every run spends a rate-limited, pay-per-use service. It also makes any later retry safe, so it must land before or with retries.

**Independent Test**: Ingest a fixture source twice and compare artifact and relationship counts and the number of embedding requests on the second run. Then change one item at the source, ingest a third time, and verify only that item changed.

**Acceptance Scenarios**:

1. **Given** a connector that has been ingested once, **When** it is ingested again with no change at the source, **Then** the artifact count and relationship count are unchanged and no embedding requests are made.
2. **Given** a connector that has been ingested once, **When** one item changes at the source and the connector is ingested again, **Then** that item's stored content is updated, only that item is re-embedded, and no duplicate is created.
3. **Given** an ingestion that failed after storing some artifacts, **When** it is run again, **Then** the result equals a single clean ingestion with no duplicates from the partial first run.
4. **Given** two ingestions of the same connector, **When** relationship extraction has run after each, **Then** each relationship between the same two artifacts exists once.
5. **Given** artifacts in two different workspaces that originate from the same external item, **When** either workspace is re-ingested, **Then** the other workspace's artifacts are untouched.

---

### User Story 3 - Keyword search finds relevant artifacts for a natural-language question (Priority: P2)

A user asks a normal question such as "how does the login retry work". Keyword retrieval returns artifacts that contain the important words of the question, even when those words are not adjacent, ranked by relevance. Keyword and similarity results are then merged so that an artifact ranked highly by both outranks one ranked highly by only one, and an artifact found by both appears once.

**Why this priority**: It affects the quality of every answer. It is P2 rather than P1 because vector retrieval already carries most questions, so today's failure is lost recall rather than wrong or unsafe output.

**Independent Test**: With a fixed set of fixture artifacts and a fixed set of questions, compare the keyword results before and after the change, and check ordering on hand-built cases where the two result lists overlap.

**Acceptance Scenarios**:

1. **Given** an artifact containing the words "login" and "retry" in different sentences, **When** the user asks "how does the login retry work", **Then** keyword retrieval returns that artifact.
2. **Given** several matching artifacts, **When** keyword retrieval returns them, **Then** they are ordered by relevance to the question, not by insertion order.
3. **Given** an artifact ranked 1st by keyword search and 1st by similarity search and another ranked 1st by only one of them, **When** the lists are merged, **Then** the first artifact is placed above the second.
4. **Given** the same artifact in both result lists, **When** they are merged, **Then** it appears once.
5. **Given** a question made only of punctuation, very common words, or characters that are special to the search syntax, **When** it is searched, **Then** the request succeeds (no error), keyword retrieval returns nothing if nothing matches, and similarity results still answer the question.
6. **Given** artifacts in several workspaces, **When** a question is searched in one workspace, **Then** only that workspace's artifacts can be returned by either retrieval path.

---

### User Story 4 - Temporary failures retry, final failures stay visible (Priority: P2)

An ingestion fails because of a temporary problem, such as a rate limit or a network error. The system retries it automatically a limited number of times with increasing delays. If a later attempt succeeds, the operator sees a completed ingestion. If every attempt fails, the operator sees a failed ingestion with the last error message and how many attempts were made. A bad credential is not retried and still shows "needs reconnect."

**Why this priority**: Today one transient error leaves a connector failed until the operator notices and manually retries. It is P2 because it is a convenience and resilience gain on top of the correctness fixes in Stories 1 to 3, and it depends on Story 2 to be safe.

**Independent Test**: Run ingestion jobs against a fake source that fails a configurable number of times, and assert the final status, attempt count, delays between attempts and the message shown.

**Acceptance Scenarios**:

1. **Given** an ingestion that fails on its first two attempts and succeeds on its third, **When** it runs, **Then** it ends as complete, records three attempts, and was never shown as failed.
2. **Given** an ingestion that fails on every attempt, **When** the maximum number of attempts is reached, **Then** it ends as failed, and the status view shows the last error message and the number of attempts.
3. **Given** an ingestion whose credential is rejected by the source, **When** it runs, **Then** it is attempted once, ends as "needs reconnect", and is not retried.
4. **Given** an ingestion waiting for its next attempt, **When** the operator views status, **Then** the connector shows that it is still in progress (not failed) and the error from the latest attempt is available.
5. **Given** consecutive retries, **When** the delays between attempts are measured, **Then** each delay is longer than the one before it.

---

### User Story 5 - Two workers never run the same job (Priority: P3)

If more than one worker process is polling the job table, each queued job is picked up by exactly one of them.

**Why this priority**: Phase 1 runs a single in-process worker, so this is not a live fault today. It is P3 because it only matters once the app runs more than one instance, which the planned hosted deployment may do (for example during a restart overlap or a scale-out).

**Independent Test**: Start two concurrent workers against a queue of many jobs and verify each job's recorded execution count is exactly one.

**Acceptance Scenarios**:

1. **Given** at least twenty queued jobs and two workers polling at the same time, **When** all jobs finish, **Then** every job ran exactly once and none ran twice.
2. **Given** one queued job and two workers polling at the same instant, **When** both try to claim it, **Then** exactly one succeeds and the other finds no job to run.
3. **Given** a job that a worker is running, **When** the other worker polls, **Then** it does not claim that job.

---

### Edge Cases

- A document's content contains text that imitates a citation marker. Citation validation must still accept only identifiers that were retrieved (covered by User Story 1, scenario 4).
- A source file is split into several stored pieces. Today every piece carries the whole file's checksum. Idempotency and "unchanged" detection must therefore treat the file as the unit: a changed file replaces all of its pieces, and an unchanged file touches none of them.
- A file shrinks and now produces fewer pieces than before. The leftover pieces from the earlier version must not remain as stale duplicates of removed content.
- The embedding service rate-limits part-way through a run, so the job fails after some artifacts were already processed. The retry must complete the run without duplicates (User Story 2, scenario 3).
- A retry is scheduled and the operator triggers ingestion manually at the same time. The operator's action must not create a second concurrent run for the same connector.
- A worker stops while a job is marked running. The job would stay running forever. Recovering these jobs is out of scope here (see Assumptions) but must not be made worse by this feature.
- An item is deleted at the source between two ingestions. Handling upstream deletion is out of scope (see Assumptions).
- Duplicate artifacts and relationships already stored by Phase 1 re-ingestions exist in any database that has been ingested more than once. Rolling out FR-006 and FR-010 must first collapse those existing duplicates, keeping the most recently ingested copy, or the uniqueness rule cannot be applied.
- A question contains characters that are meaningful to search syntax (quotes, minus signs, ampersands, parentheses). It must not cause an error or change which workspace is searched.

## Requirements *(mandatory)*

### Functional Requirements

**Untrusted-content boundary**

- **FR-001**: Every field of a retrieved artifact that is placed in the model request (content, title, type, origin, source address, identifier) MUST be neutralized so that no value can end the evidence section, begin an additional item, or change another field's value.
- **FR-002**: The fixed instruction portion of the model request MUST continue to contain no retrieved content.
- **FR-003**: The test suite MUST include an adversarial set of at least eight distinct break-out patterns (closing the section, injecting a fake item, ending an attribute early, nested or malformed markup, markup in each of the fields in FR-001, and text imitating the citation marker), each asserting that the rendered structure matches what was retrieved.
- **FR-004**: Citation validation and abstention behavior MUST remain unchanged: only identifiers present in the retrieved set are returned as citations, and an answer with no valid citation is an abstention.

**Idempotent ingestion**

- **FR-005**: An artifact's identity MUST be stable across ingestions of the same source within a workspace, so that ingesting the same source item again refers to the same stored artifact.
- **FR-006**: The system MUST prevent two stored artifacts from having the same identity within a workspace, so that duplicates cannot be created by any code path, including concurrent runs.
- **FR-007**: When an ingestion encounters an item whose identity already exists and whose content checksum is unchanged, the system MUST leave the stored artifact as it is and MUST NOT request a new embedding for it.
- **FR-008**: When an ingestion encounters an item whose identity exists but whose content has changed, the system MUST update the stored artifact in place and re-embed only that item.
- **FR-009**: When a source file's stored pieces change in number, the system MUST end with exactly the pieces of the current version of the file and no leftovers from the previous version.
- **FR-010**: Relationship extraction MUST be idempotent: running it any number of times on the same artifacts yields each relationship (same source, target and type) exactly once.
- **FR-011**: A run that fails part-way MUST leave the workspace in a state from which a re-run produces the same result as one clean run.

**Ranked keyword search and merged results**

- **FR-012**: Keyword retrieval MUST match on the meaningful words of the question rather than the whole question as one substring, so that a question matches an artifact containing those words anywhere in its title or content.
- **FR-013**: Keyword results MUST be ordered by relevance to the question.
- **FR-014**: The keyword and similarity result lists MUST be merged by combining each artifact's rank in each list, so that an artifact ranked well by both outranks one ranked well by only one. An artifact present in both lists MUST appear once in the merged result.
- **FR-015**: A question consisting only of punctuation, ignorable words, or characters that are special to the search syntax MUST NOT cause an error, and MUST NOT prevent similarity results from being returned.
- **FR-016**: Both retrieval paths MUST remain scoped to the requesting workspace in every case (Constitution Principle VI).

**Retry and visibility**

- **FR-017**: A failed ingestion job MUST be retried automatically up to a fixed maximum number of total attempts, with a delay before each retry that is longer than the delay before the previous one.
- **FR-018**: A credential rejection from the source MUST NOT be retried. The connector MUST end in the existing "needs reconnect" state after one attempt.
- **FR-019**: While a job has attempts remaining, the connector's status MUST show that ingestion is still in progress and MUST NOT show it as failed.
- **FR-020**: When the final attempt fails, the job and the connector MUST both end as failed, and the status view MUST show the last error message and the number of attempts made.
- **FR-021**: The job status response MUST include the attempt count so that the status view can show it.
- **FR-022**: Requesting ingestion for a connector that already has a queued, running or waiting-to-retry job MUST NOT create a second concurrent job for that connector.

**Safe job claiming**

- **FR-023**: When several workers poll the job table at the same time, each queued job MUST be claimed by exactly one worker.
- **FR-024**: Claiming a job MUST NOT block other workers from claiming different jobs.

**Constraints that apply to the whole feature**

- **FR-025**: The feature MUST NOT introduce a new external service or paid dependency (Constitution, Technology Constraints; $0 budget).
- **FR-026**: Existing behavior covered by the current test suite (citation validation, abstention, workspace isolation, token encryption, prompt isolation) MUST keep passing without edits to the assertions.
- **FR-027**: Documentation that describes any behavior changed here (`README.md` Known limitations, `docs/roadmap.md`, ADR-001 consequences) MUST be updated in the same change.

### Key Entities *(include if feature involves data)*

- **Ingestion Job**: A request to ingest one connector. Has a status (queued, running, waiting to retry, complete, failed), an attempt count, the last error message, and the time of the next attempt when one is scheduled. Each connector has at most one active job at a time (FR-022).
- **Artifact**: One stored, embeddable piece of source content. Its identity is the combination of workspace, source system and the source item's own identifier, and it carries a content checksum used to detect change. A source file may be stored as several pieces that are replaced together.
- **Relationship**: A deterministic link between two artifacts. Unique per workspace by source artifact, target artifact and type.
- **Evidence Item**: One retrieved artifact as presented to the model, with its identifying fields and its content. Everything inside it is data, never instructions.
- **Retrieval Result List**: An ordered list of artifacts from one retrieval path (keyword or similarity). Two lists are merged into one ranked list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ingesting an unchanged source a second time produces zero new artifacts, zero new relationships, and zero embedding requests.
- **SC-002**: After changing one item at the source, a re-ingestion changes exactly that item (one artifact updated, one embedding request) and nothing else.
- **SC-003**: Every case in the adversarial set (at least eight patterns) produces an evidence section whose item count and field values equal what was retrieved.
- **SC-004**: With two workers and at least twenty queued jobs, every job runs exactly once, in repeated runs of the test.
- **SC-005**: A job that fails transiently twice and then succeeds ends complete after three attempts. A job that always fails ends failed after the maximum attempts with its last error visible. A rejected credential ends "needs reconnect" after exactly one attempt.
- **SC-006**: On the manual validation question set from `docs/prd.md` §7, keyword retrieval returns the known-relevant artifact for more questions than the baseline measured before this change, and no question that passed before now fails.
- **SC-007**: The full existing test suite passes with no changed assertions, and every new behavior above is covered by at least one new automated test.

## Assumptions

- The maximum number of attempts and the retry delays are proposed defaults to be fixed in `plan.md` (proposed: three total attempts, with delays that at least double). They are not product decisions.
- The "adversarial set of at least eight patterns" and "at least twenty jobs" are proposed minimums chosen for this spec, not measured requirements.
- Phase 1 runs one in-process worker. Safe claiming (User Story 5) is protective for the planned hosted deployment and is the lowest priority.
- Recovering a job left in the running state after a worker crash is out of scope. It is a real gap closely related to this feature and is recorded as a follow-up, not silently dropped.
- Items deleted at the source stay in ContextOS after re-ingestion, because there is no incremental sync. Removing them is a separate decision.
- No change is made to the generation or embedding providers, the answer format, the citation rules, or abstention behavior.
- Migrations for this feature touch the artifact, relationship and job tables, and the connector status values if a "retrying" state is added. Feature 002 changes the connector table (installation identifier, nullable token). The two features therefore both migrate the connector side, so they should not be merged in an order that makes their migrations conflict. Migration ordering is a planning concern for whichever is built second.
- The existing retry inside the embedding client for rate limits is kept. The new job-level retry sits on top of it and is not a replacement.
- Deployment is not required for this feature to be complete. All acceptance scenarios are testable locally.
- The question set and baseline for SC-006 are recorded before any retrieval change is made, so the comparison is real.
- Collapsing existing duplicates (see Edge Cases) is a one-time data cleanup that is part of this feature's rollout. It must be reviewed against a copy of real data before it is run, because it deletes rows.
