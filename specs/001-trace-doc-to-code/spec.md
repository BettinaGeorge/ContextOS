# Feature Specification: Trace a Spec/Doc to Code

**Feature Branch**: `001-trace-doc-to-code`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Phase 1 MVP (docs/prd.md §3-§5): let a user connect one GitHub repository and one Notion workspace, sign in, ingest artifacts from both, and ask questions that require tracing a written spec/doc to the code that implements it — getting an answer that cites its sources, distinguishes evidence from inference, and explicitly says so when it doesn't have enough evidence. Single user, single workspace, single repo, single Notion source. No incremental sync, no other workflows in this phase."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect tools and get a cited answer (Priority: P1)

As an engineer new to a codebase, I sign in, create a workspace, connect a GitHub repository and a Notion workspace, and ask a question like "what code implements this doc?" so I get a cited, evidence-backed answer without manually cross-referencing both tools myself.

**Why this priority**: This is the entire MVP — the core value loop the product exists to prove. Nothing else in this feature matters if this doesn't work end to end.

**Independent Test**: Can be fully tested by connecting both tools to a small real repo + Notion set, asking one question about a doc with a known deterministic link to a PR, and verifying the citation appears correctly.

**Acceptance Scenarios**:

1. **Given** a signed-in user with no workspace, **When** they create a workspace and connect GitHub + Notion, **Then** both connectors reach a successful, ingested state.
2. **Given** a Notion doc containing an explicit link to a GitHub PR, **When** the user asks a question referencing that doc, **Then** the response cites that PR with a direct, openable link.
3. **Given** a Notion doc with no explicit link to any GitHub artifact, **When** the user asks about it, **Then** the response either surfaces semantically related code labeled as inferred, or explicitly states no confident match was found — never presents a guess as certain.

---

### User Story 2 - Evidence discipline: abstain rather than guess (Priority: P2)

As a user relying on ContextOS to make a responsible decision, if there is no relevant evidence for my question, I want the system to say so rather than fabricate an answer.

**Why this priority**: The core trust differentiator (constitution principle I), but it's secondary to User Story 1 in build order — it's tested against the same ingestion/retrieval path once that exists, using questions chosen to have no answer.

**Independent Test**: Ask a question with no relevant ingested content and confirm the system explicitly abstains instead of inventing a citation.

**Acceptance Scenarios**:

1. **Given** a workspace with ingested content unrelated to the question asked, **When** the user asks that question, **Then** the response states that evidence is insufficient and cites nothing.
2. **Given** any response containing a citation, **When** that citation is checked against what was actually retrieved, **Then** the cited source demonstrably supports the specific claim next to it — zero tolerance for fabricated citations.

---

### User Story 3 - Ingestion status visibility (Priority: P3)

As a user who just connected GitHub or Notion, I want to see whether ingestion succeeded or failed so I know whether the system is ready to answer questions.

**Why this priority**: A quality-of-life and trust requirement — User Stories 1-2 are technically verifiable without a polished status UI, but a user can't use the product with confidence without knowing ingestion actually finished.

**Independent Test**: Connect a repo and observe ingestion status transition from in-progress to complete, and separately, trigger a failure (e.g. revoked token) and observe a clear failure state.

**Acceptance Scenarios**:

1. **Given** a newly connected GitHub repository, **When** ingestion is running, **Then** the user can see an in-progress status.
2. **Given** an ingestion failure, **When** the user views the connector, **Then** a clear error state and reason are shown, not a silent hang.

---

### Edge Cases

- What happens when a Notion doc is edited after ingestion but before a question is asked (stale content)? Out of scope for incremental sync in this phase (see PRD §10, open question); the answer reflects the last-ingested snapshot, with no requirement to detect staleness yet.
- What happens when a Notion doc and GitHub PR are related but the user didn't follow the deterministic-link convention (PRD §4)? Falls under User Story 2 — semantic fallback labeled as inferred, or explicit abstention.
- What happens if GitHub or Notion authorization is revoked mid-session? The connector shows a failed/needs-reconnect state (User Story 3); previously ingested data remains queryable, but re-ingestion fails until reconnected.
- What happens if a user asks a question not clearly anchored to any specific Notion doc? Building a general open-ended "explore the repo" workflow is out of scope for this phase (that's a later roadmap phase); the system may still attempt best-effort retrieval, but there's no acceptance criterion requiring it to succeed — abstaining is an acceptable outcome if no anchor can be identified.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a user to sign in and create exactly one workspace.
- **FR-002**: System MUST allow a signed-in user to connect exactly one GitHub repository to their workspace.
- **FR-003**: System MUST allow a signed-in user to connect exactly one Notion workspace/integration, scoped to pages the user selects, to their workspace.
- **FR-004**: System MUST perform a full (non-incremental) ingestion of GitHub repository files, pull requests, commits, issues, and contributors upon connection.
- **FR-005**: System MUST perform a full ingestion of the selected Notion pages/blocks upon connection.
- **FR-006**: System MUST normalize ingested GitHub and Notion artifacts into the shared artifact model (docs/prd.md §6).
- **FR-007**: System MUST extract a deterministic relationship between a Notion doc and a GitHub artifact when a GitHub PR/commit link is present in the Notion doc content, or a Notion page URL is present in a PR/commit description.
- **FR-008**: System MUST support retrieval combining full-text (keyword) search and vector similarity search over ingested artifacts.
- **FR-009**: Users MUST be able to submit a natural-language question referencing (or implying) a specific Notion doc and receive a synthesized answer.
- **FR-010**: System MUST include inline source citations, linking back to the originating GitHub or Notion URL, for every factual claim in a generated answer.
- **FR-011**: System MUST label any relationship or evidence used in an answer that was not deterministically linked as inferred, and MUST NOT present it with the same certainty as a deterministic link.
- **FR-012**: System MUST respond with an explicit statement of insufficient evidence when no relevant ingested content is found, rather than generating an unsupported answer.
- **FR-013**: System MUST NOT include a citation to a source that was not actually retrieved as evidence for the claim it's attached to.
- **FR-014**: System MUST show ingestion status (in progress / complete / failed with reason) for each connector.
- **FR-015**: System MUST treat all ingested content (repository files, commit messages, PR descriptions, Notion page content) as untrusted data, never as instructions to the underlying model.
- **FR-016**: System MUST encrypt connector authentication tokens at rest and MUST NOT log them in plaintext.
- **FR-017**: System MUST scope all stored artifacts and relationships by workspace, even though only one workspace is exercised in this phase.

### Key Entities

- **Workspace**: The isolation boundary for a user's connected tools and ingested data. Owns exactly one GitHub connection and one Notion connection in this phase.
- **Artifact**: A normalized representation of an ingested item (`source_file`, `commit`, `pull_request`, `issue`, `document`) per the canonical model in docs/prd.md §6 — carries source system, source URL, author, timestamps, and content.
- **Relationship**: A directed link between two artifacts (e.g., document → pull_request), carrying an origin (`explicit` or `metadata-derived` in this phase) and, when inferred, a confidence/evidence note.
- **Connector**: A connection to an external system (GitHub or Notion) with its own authorization state and ingestion status, scoped to one workspace.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from sign-in to receiving one cited, evidence-backed answer without any manual intervention in the underlying data.
- **SC-002**: Zero fabricated citations occur across a manually validated set of at least 10 test questions.
- **SC-003**: At least 7 of 10 hand-written test questions receive a correctly-cited, genuinely useful answer; the remaining questions may correctly abstain when evidence is legitimately missing — abstention on a truly unanswerable question counts as success, not failure.
- **SC-004**: Every response that includes a citation links to a URL a user can open to independently verify the claim.
- **SC-005**: A user can determine, without leaving the product, whether their connected tools finished ingesting or failed, within seconds of checking.

## Assumptions

- Single user, single workspace, single GitHub repository, single Notion source for this phase (docs/prd.md §1).
- The Notion-to-GitHub deterministic-link convention (pasting a link in the doc, or referencing the doc URL in a PR/commit) is followed manually by the user; the system does not enforce or prompt for it in this phase.
- Incremental sync/webhooks are out of scope; reconnecting or re-ingesting is a manual, full re-ingestion.
- Code chunking granularity (naive vs. function/class-boundary) is an implementation-plan-level decision, not fixed by this spec.
- Team invites and multi-user collaboration UI are out of scope, even though the underlying data model is workspace-isolated from day one.
- Jira and any other connector are out of scope for this feature.
