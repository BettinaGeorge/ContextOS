# Feature Specification: OAuth Connectors & Project Dashboard

**Feature Branch**: `002-oauth-connectors-dashboard`

**Created**: 2026-07-23

**Status**: Draft

**Input**: User description: "Replace ContextOS's manual-token onboarding with an OAuth-based, multi-project experience, closing the open question recorded in docs/prd.md §10 ('Connector token acquisition: manual PAT vs Supabase OAuth providers'). Three coupled pieces: (1) multi-provider sign-in (Google/GitHub OAuth alongside existing magic-link email), (2) OAuth-based connector setup for GitHub and Notion (authorize-and-pick, replacing pasted tokens and typed owner/repo strings), (3) a project dashboard as the new home surface (overview of the user's workspaces, an 'Add new project' flow), which requires a user to be able to own more than one workspace — a change from Phase 1's single-workspace-per-user assumption."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect a GitHub repo without typing anything (Priority: P1)

A signed-in user with no GitHub connector yet clicks "Connect GitHub." Instead of a form asking for an `owner/repo` string and a pasted personal access token, they're taken through GitHub's own OAuth consent screen. After authorizing, they land back in ContextOS on a list of the repositories they can access and pick the one they want. No token is ever typed or pasted by the user.

**Why this priority**: This is the single highest-friction point in the current product — confirmed directly by real use (manual PAT setup caused repo-scoping errors and org-approval gates during Phase 1 testing, and a live walkthrough of the current Connect page during this feature's own discovery independently hit the same "I don't want to type all this" friction). It's also the one the PRD already flagged as a deferred decision (§10) waiting for exactly this moment.

**Independent Test**: Can be fully tested by a user with a GitHub account and at least one repository: start from a workspace with no GitHub connector, complete the OAuth flow, and verify a connector row exists pointing at the selected repo with a working (encrypted, decrypted-at-use) access token — deliverable and demoable on its own even before Notion OAuth or the dashboard exist.

**Acceptance Scenarios**:

1. **Given** a signed-in user on a workspace with no GitHub connector, **When** they click "Connect GitHub" and complete GitHub's consent screen, **Then** they see a list of repositories they can access and can select exactly one.
2. **Given** a user has selected a repository from the picker, **When** the selection is confirmed, **Then** a GitHub connector is created for that workspace scoped to that repository, without the user ever seeing or typing a token.
3. **Given** a user cancels or denies GitHub's consent screen, **When** they're returned to ContextOS, **Then** they see a clear message that the connection wasn't completed and can retry — no partial/broken connector is created.
4. **Given** a workspace already has a connected GitHub repository, **When** the user views the Connect page, **Then** they see which repository is connected and an option to disconnect/reconnect, not the picker again.

---

### User Story 2 - Connect a Notion workspace without typing anything (Priority: P2)

Same shape as User Story 1, for Notion: click "Connect Notion," authorize via Notion's OAuth consent screen, then pick which pages (or the whole shared workspace) to connect from a list — no pasted integration token, no manually typed page IDs.

**Why this priority**: Second-highest friction point today, same category of problem as GitHub's, but ships after GitHub OAuth since it reuses the same authorize-and-pick pattern and isn't blocking Story 1's value on its own.

**Independent Test**: Can be fully tested independently of GitHub OAuth or the dashboard — a user with a Notion account can complete the OAuth flow and verify a Notion connector is created pointing at the pages they selected.

**Acceptance Scenarios**:

1. **Given** a signed-in user on a workspace with no Notion connector, **When** they click "Connect Notion" and complete Notion's consent screen, **Then** they see a list of pages/databases shared with the integration and can select which ones to connect.
2. **Given** a user has selected pages, **When** the selection is confirmed, **Then** a Notion connector is created for that workspace scoped to those pages, without the user ever seeing or typing a token or page ID.
3. **Given** a user cancels or denies Notion's consent screen, **When** they're returned to ContextOS, **Then** they see a clear message that the connection wasn't completed and can retry.

---

### User Story 3 - See all projects from one home screen (Priority: P3)

Instead of landing directly inside a single workspace, a signed-in user's home page shows an overview of every workspace ("project") they own — each with an at-a-glance connection/ingestion status — plus an "Add new project" action that starts a fresh workspace and walks straight into the OAuth connect flow (Stories 1 and 2) for it.

**Why this priority**: Delivers real value once a user has more than one project, but a user with only one workspace still gets full value from Stories 1 and 2 without this — it's the structural container, not the core friction fix.

**Independent Test**: Can be tested independently by creating two workspaces for one user and verifying the home page lists both with correct status, and that "Add new project" creates a third and routes into the connect flow — testable even if the connect flow underneath still used the old manual-token forms.

**Acceptance Scenarios**:

1. **Given** a signed-in user who owns zero workspaces, **When** they land on the home page, **Then** they see an empty state prompting them to add their first project.
2. **Given** a signed-in user who owns two or more workspaces, **When** they land on the home page, **Then** they see all of them listed with each one's connector/ingestion status visible without opening it.
3. **Given** a user on the home page, **When** they click "Add new project," **Then** a new workspace is created and they're taken directly into connecting GitHub/Notion for it.
4. **Given** a user selects an existing project from the dashboard, **When** they open it, **Then** they land on that workspace's own status/ask views (unchanged from Phase 1), not a shared/ambiguous context.

---

### User Story 4 - Sign in with Google or GitHub (Priority: P4)

Alongside the existing magic-link email sign-in, a user can sign in with a single click via Google or GitHub, matching the familiar "continue with" pattern from tools like Vercel.

**Why this priority**: Lowest priority of the four — magic-link email sign-in already works today, so this is a conversion/convenience improvement, not a fix to something broken. Independent of all three stories above.

**Independent Test**: Can be tested in isolation: a new user completes "Continue with Google" (or GitHub) and lands signed in with a session, without touching connectors or the dashboard at all.

**Acceptance Scenarios**:

1. **Given** a user on the sign-in page, **When** they click "Continue with Google," **Then** they complete Google's consent screen and return to ContextOS signed in.
2. **Given** a user on the sign-in page, **When** they click "Continue with GitHub," **Then** they complete GitHub's consent screen and return to ContextOS signed in.
3. **Given** a user who previously signed in via magic-link email, **When** they later sign in with Google/GitHub using the same email address, **Then** they land on the same account (no duplicate account created) — resolved: identities with a matching, confirmed email MUST always merge into one account, never silently create a second one.

### Edge Cases

- What happens when a user's GitHub OAuth grant is revoked externally (e.g., they remove ContextOS's access from GitHub settings) after a repo is already connected? Ingestion should fail visibly with a reconnect prompt (existing `needs_reconnect` status from Phase 1's ingestion-failure-visibility work applies here, not a new state).
- What happens if a user picks a repository during the OAuth picker step that they no longer have access to by the time they confirm (e.g., access revoked mid-flow)? The confirmation must fail with a clear error, not silently create a broken connector.
- What happens when a user tries to connect a second GitHub repository to a workspace that already has one? Phase 1's one-repo-per-workspace constraint (PRD §4) is unchanged by this feature — the picker flow still only ever results in one connected repo per workspace.
- How does the system handle a user who owns zero workspaces landing on the dashboard for the very first time (new signup)? Covered by User Story 3, Scenario 1.
- What happens if OAuth token acquisition succeeds but the immediate repo/page listing call fails (rate limit, transient network error)? The user should see a retry option, not a dead end requiring them to restart the entire OAuth consent flow.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to sign in via Google OAuth and GitHub OAuth, in addition to the existing magic-link email sign-in.
- **FR-002**: Users MUST be able to connect a GitHub repository via an authorize-then-pick flow — no manually typed `owner/repo` string and no manually pasted personal access token in the primary path.
- **FR-003**: Users MUST be able to connect Notion pages via an authorize-then-pick flow — no manually pasted integration token and no manually typed page IDs in the primary path.
- **FR-004**: The system MUST continue to store every connector access token encrypted at rest and decrypt only at point of use (Constitution Principle III) — this feature changes how a token is acquired, not how it is stored.
- **FR-005**: The system MUST present a home dashboard listing every workspace ("project") the signed-in user owns, each showing its connector/ingestion status.
- **FR-006**: Users MUST be able to start an "add new project" flow from the dashboard that creates a new workspace and proceeds directly into the GitHub/Notion connect flow (FR-002/FR-003) for it.
- **FR-007**: A user MUST be able to own more than one workspace — Phase 1's single-workspace-per-user assumption no longer holds after this feature.
- **FR-008**: If a user denies or cancels an OAuth consent screen (sign-in or connector), the system MUST return them to a clear, actionable state — not a partially-created account or connector.
- **FR-009**: The system MUST NOT introduce team membership, workspace sharing, or multi-user collaboration on a single workspace as part of this feature — multiple *owned* workspaces per user is in scope; *shared* workspaces remain out of scope (deferred to roadmap Phase 6, "real team/invite UI").

### Key Entities

- **Workspace ("Project")**: Unchanged shape from Phase 1, except its relationship to a user changes from one-to-one to one-to-many (one user can own many workspaces; each workspace still has exactly one owner).
- **OAuth Connection**: A new concept representing a completed provider authorization (GitHub or Notion) that has not yet been narrowed to a specific connector selection — exists transiently between "user authorized" and "user picked a repo/pages," distinct from the `Connector` entity (which represents the final, scoped, encrypted-token connection Phase 1 already defined).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from "no GitHub connector" to "repository connected and ingestion started" without typing or pasting any credential, in under 60 seconds of interaction time.
- **SC-002**: A user can go from "no Notion connector" to "pages connected and ingestion started" without typing or pasting any credential, in under 60 seconds of interaction time.
- **SC-003**: A user who owns 3+ projects can identify which ones need attention (failed/needs-reconnect status) from the dashboard alone, without opening each one individually.
- **SC-004**: Zero support-relevant setup errors of the class already observed in Phase 1 manual testing (repo scoping errors, missing-permission errors, org-approval-gate confusion) occur during the OAuth connect flow, since the picker only ever shows repositories/pages the user actually has access to.
- **SC-005**: A new user can create their first project and reach a connected, ingesting state entirely through one-click/point-and-click actions, with zero required free-text input beyond naming the project.

## Assumptions

- Sign-in OAuth (Google/GitHub, for authentication) and connector OAuth (GitHub/Notion, for repository/page access) are treated as **separate concerns that may use separate OAuth apps/scopes** — signing in with GitHub does not by itself grant repository access, and connecting a GitHub repository does not by itself change how the user signs in. This mirrors how Vercel and similar tools separate account identity from source-control app installation. The exact mechanism (Supabase Auth providers for sign-in vs. a dedicated GitHub OAuth App for repo access) is an implementation decision for `/speckit-plan`, not this spec.
- GitHub's OAuth `repo` scope grants access to all of a user's repositories, not just the one selected — this is the same trade-off already documented in `docs/prd.md` §10 as accepted (broader grant than a fine-scoped PAT) in exchange for removing manual setup friction. Not re-litigated here.
- Phase 1's one-repository-per-workspace and one-Notion-source-per-workspace constraints (PRD §4) are unchanged by this feature. Multi-repo-per-workspace remains out of scope (still roadmap Phase 6).
- "Project" in user-facing language and "Workspace" in the existing data model refer to the same entity — this feature does not introduce a new distinct entity, only a new cardinality (one user, many workspaces) and a new home surface for browsing them.
- Team/shared workspace access is explicitly out of scope (see FR-009) — each workspace still has exactly one owner after this feature.
- Existing manual PAT/integration-token entry is removed from the primary Connect page flow once OAuth is available, not kept as a secondary "advanced" option — consistent with the request that no user should have to type this information. Revisiting a manual fallback (e.g., for GitHub orgs that restrict third-party OAuth app installation) is deferred unless real usage surfaces that need, matching how this project already handles deferred decisions.
