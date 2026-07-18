# ContextOS — Claude Code Project Handoff

## 1. Project Summary

**Project name:** ContextOS  
**Working tagline:** The engineering context engine for software teams.

ContextOS is an AI-native platform that connects the tools used by software engineering and product teams—such as GitHub, Jira, Figma, FigJam, Notion, Confluence, Slack, Linear, Google Drive, Sentry, Datadog, and related systems—and transforms fragmented organizational knowledge into a connected, evidence-backed understanding of a product or codebase.

The core problem is not that teams lack information. The problem is that important context is scattered across many platforms, formats, and conversations. Engineers often need to reconstruct how a feature works, why a decision was made, which design is current, which ticket introduced a change, who owns a service, or which documents are relevant to a task.

ContextOS should help users answer those questions without manually searching through every tool.

It is **not** intended to be another generic chatbot, coding copilot, or enterprise search clone. Its core value is cross-platform context reconstruction, evidence-backed reasoning, and task-specific guidance.

---

## 2. Founder / Builder Context

The builder is Bettina George, a Computer Science and Information Science student at UNC-Chapel Hill graduating in May 2027.

Relevant background:

- Two-time Software Engineering Intern at Lowe’s
- Experience with Java, Spring Boot, React, TypeScript, FastAPI, Kafka, PostgreSQL, MongoDB, APIs, and event-driven systems
- Designed an AI-assisted, specification-driven development workflow using GitHub Spec Kit and Devin
- Built RAG systems, multi-tool agents, content classifiers, moderation APIs, vector search systems, evaluation pipelines, and prompt-injection defenses through CodePath’s AI Engineering program
- Built and evaluated ML systems through KPMG + Break Through Tech
- Experience onboarding into unfamiliar systems, working across technical teams, contributing to open source, participating in hackathons, and helping beginner programmers debug as a teaching assistant
- Strong interest in AI engineering, developer productivity, reliable LLM systems, user-centered products, and scalable engineering systems

The project comes from a problem the builder has personally experienced: entering an unfamiliar technical environment and needing to understand how code, requirements, design decisions, tickets, documents, and team conversations fit together before making responsible changes.

The product should feel authentic to that experience rather than like a project built solely to impress recruiters.

---

## 3. Product Vision

ContextOS should become the intelligence layer across an engineering team’s tools.

A user should be able to connect the platforms their team already uses and ask questions such as:

- How does authentication work?
- Why was this architectural decision made?
- Which Figma design corresponds to this feature?
- Which Jira ticket introduced this behavior?
- Which pull request implemented this requirement?
- What will be affected if I change this service?
- Which documents should I read before fixing this bug?
- Is the current documentation consistent with the code?
- Who owns this component?
- What changed recently?
- Which requirements remain unimplemented?
- What context is most relevant to the task I am working on?

ContextOS should answer using traceable evidence from connected sources.

A high-quality answer should not merely summarize documents. It should reconstruct relationships among artifacts.

Example relationship chain:

Figma design  
→ FigJam brainstorming board  
→ Jira epic  
→ engineering specification  
→ pull request  
→ commits  
→ source code  
→ documentation  
→ Slack discussion  
→ monitoring incident

---

## 4. Core Product Principle

**AI should help users build an accurate mental model before they act.**

ContextOS should prioritize understanding, evidence, and uncertainty over fast but unsupported answers.

The product should:

- Cite sources
- Distinguish facts from inferences
- Show uncertainty when evidence is incomplete
- Avoid inventing relationships
- Explain why a source is relevant
- Preserve access controls from connected systems
- Help users narrow their attention to the most relevant context
- Support different tasks rather than providing only a generic chat interface

---

## 5. Target Users

### Primary users

1. **New engineers joining an existing team**
   - Need to understand architecture, ownership, conventions, and past decisions
   - Often overwhelmed by scattered documentation and unfamiliar code

2. **Engineers switching teams or services**
   - Need rapid context on a new domain
   - Must understand dependencies and historical decisions

3. **Early-career engineers and interns**
   - Need guidance identifying what information matters
   - May not know where organizational knowledge is stored

4. **Engineers implementing features or fixing bugs**
   - Need to gather related tickets, designs, specs, code, discussions, and ownership information

5. **Engineering managers and technical leads**
   - Need visibility into project context, knowledge gaps, stale documentation, and risk

### Secondary users

- Product managers
- Designers
- Developer advocates
- Support engineers
- Site reliability engineers
- Technical program managers

---

## 6. Primary User Jobs

A user may enter ContextOS with one of the following intents:

- Understand a codebase
- Onboard to a team
- Fix a bug
- Build a feature
- Review a pull request
- Investigate an incident
- Understand a service
- Find the origin of a decision
- Trace a requirement to implementation
- Identify ownership
- Find relevant context for a ticket
- Detect stale or conflicting documentation

The product should eventually support intent-specific workflows rather than treating every request as generic question answering.

---

## 7. Product Differentiation

ContextOS should not be positioned as:

- A generic “chat with your documents” tool
- A basic RAG application
- A code completion tool
- A direct Cursor or Copilot clone
- A simple internal search engine
- A tool that connects platforms but merely displays results
- A chatbot that produces answers without evidence

Its differentiation should be:

1. **Cross-platform engineering context**
2. **Relationship-aware retrieval**
3. **Task-specific context assembly**
4. **Evidence-backed answers**
5. **Temporal reasoning**
6. **Code-aware and design-aware understanding**
7. **Source freshness and conflict detection**
8. **Access-control-aware retrieval**
9. **Actionable context, not just summaries**

---

## 8. MVP Scope

The MVP should be deliberately narrow.

### MVP objective

Allow a user to connect a GitHub repository and one project-management or documentation source, then ask evidence-backed questions that link code to product context.

### Recommended first two connectors

1. GitHub
2. Jira

GitHub provides:
- Repositories
- Source files
- Pull requests
- Issues
- Commits
- Contributors
- File history
- Code ownership signals

Jira provides:
- Epics
- Stories
- Tasks
- Bugs
- Acceptance criteria
- Status
- Assignees
- Labels
- Linked tickets
- Comments

### Optional alternative

GitHub + Notion may be easier for an early prototype, but GitHub + Jira better demonstrates the intended engineering workflow.

### MVP user flow

1. User creates an account
2. User creates a workspace
3. User connects GitHub
4. User selects a repository
5. User connects Jira
6. User selects a Jira project
7. ContextOS ingests and indexes available artifacts
8. User chooses a workflow:
   - Understand a feature
   - Fix a bug
   - Explore architecture
   - Trace a requirement
9. User enters a question or ticket ID
10. ContextOS retrieves relevant evidence
11. ContextOS returns:
   - A synthesized explanation
   - Source citations
   - Relevant files
   - Related tickets
   - Related pull requests or commits
   - Confidence or evidence-strength indicators
   - Gaps or unresolved questions

---

## 9. MVP Functional Requirements

### Authentication and workspaces

- Users can sign in
- Users can create a workspace
- A workspace can store multiple connector configurations
- Connector credentials must be stored securely
- Data must be isolated by workspace

### GitHub connector

- Authenticate through GitHub OAuth or a GitHub App
- Select repositories
- Ingest repository metadata
- Ingest source files
- Ingest pull requests
- Ingest commits
- Ingest issues
- Store references to source URLs
- Support incremental updates
- Respect repository permissions

### Jira connector

- Authenticate to Jira
- Select Jira projects
- Ingest issues, epics, stories, bugs, comments, status, assignees, and links
- Store references to source URLs
- Support incremental updates
- Respect Jira permissions

### Ingestion

- Normalize data from different connectors into a common artifact model
- Preserve source metadata
- Preserve timestamps
- Preserve authorship
- Preserve parent-child relationships
- Preserve external URLs
- Track ingestion status and errors
- Allow re-indexing

### Retrieval

- Support keyword search
- Support semantic retrieval
- Support metadata filtering
- Support source-type filtering
- Support recency filtering
- Support relationship-aware retrieval
- Retrieve code using symbol-aware or structure-aware chunking where feasible

### Answer generation

- Every factual claim should be traceable to one or more sources when possible
- Responses should distinguish:
  - Direct evidence
  - Inference
  - Missing information
- Answers should include source links
- Answers should not claim certainty when sources conflict
- Answers should be able to say that available evidence is insufficient

### Task-specific workflows

Initial workflow options:

1. **Understand a feature**
2. **Fix a bug**
3. **Trace a Jira ticket to code**
4. **Explore repository architecture**

### Context graph

The MVP should create explicit relationships where confidently supported, including:

- Jira issue → pull request
- Pull request → commit
- Commit → file
- Issue → issue
- File → file dependency
- Pull request → author
- Ticket → assignee
- Ticket → epic

Relationships may come from:
- Explicit IDs in branch names or commit messages
- Pull request metadata
- Linked Jira issues
- Code imports
- Repository structure
- Human confirmation

Inferred relationships must be labeled as inferred.

---

## 10. Future Connectors

The connector framework should eventually support:

### Code and source control
- GitHub
- GitLab
- Bitbucket

### Project management
- Jira
- Linear
- Asana
- Trello
- Monday.com

### Design
- Figma
- FigJam
- Miro

### Documentation
- Notion
- Confluence
- Google Drive
- Google Docs
- SharePoint

### Communication
- Slack
- Microsoft Teams
- Discord

### Observability
- Sentry
- Datadog
- New Relic
- Grafana
- PagerDuty

### Product and support
- Productboard
- Zendesk
- Intercom
- LaunchDarkly

### Meetings and video
- Zoom transcripts
- Google Meet transcripts
- Loom

The product should not attempt to implement all of these in the first release.

---

## 11. Connector Architecture Requirements

The connector framework should be designed so new integrations can be added without changing the core retrieval and reasoning system.

Each connector should implement a common interface such as:

- authenticate()
- validate_connection()
- list_available_resources()
- ingest_full()
- ingest_incremental()
- normalize_artifact()
- normalize_relationship()
- revoke()
- health_check()

Each connector should define:

- Source type
- Authentication method
- Supported artifact types
- Rate-limit behavior
- Pagination behavior
- Webhook support
- Incremental-sync strategy
- Permission model
- Error-handling strategy
- Data-retention behavior

Connector-specific logic should remain isolated from the core domain layer.

---

## 12. Canonical Data Model

The system should use a normalized artifact model.

### Artifact

Suggested fields:

- id
- workspace_id
- source_system
- source_artifact_id
- artifact_type
- title
- content
- structured_content
- author
- created_at
- updated_at
- source_url
- parent_id
- permissions
- metadata
- checksum
- ingestion_version
- deleted_at

### Artifact types

Examples:

- source_file
- symbol
- commit
- pull_request
- issue
- jira_ticket
- epic
- comment
- design
- design_node
- document
- message
- incident
- alert
- specification
- meeting_transcript

### Relationship

Suggested fields:

- id
- workspace_id
- source_artifact_id
- target_artifact_id
- relationship_type
- confidence
- evidence
- relationship_origin
- created_at
- updated_at

### Relationship origins

- explicit
- metadata-derived
- code-derived
- model-inferred
- user-confirmed

---

## 13. AI and Retrieval Design

ContextOS should use retrieval-augmented generation, but RAG alone is not the product.

Recommended retrieval pipeline:

1. Interpret user intent
2. Extract entities:
   - Ticket IDs
   - Repository names
   - File names
   - Services
   - Teams
   - Features
3. Retrieve exact matches
4. Retrieve semantic matches
5. Traverse graph relationships
6. Apply metadata and permission filters
7. Rank evidence
8. Detect conflicts
9. Build an evidence packet
10. Generate a response grounded only in the evidence packet
11. Validate citations
12. Return answer, sources, uncertainty, and gaps

### Retrieval strategies

- BM25 or full-text search
- Dense-vector retrieval
- Hybrid retrieval
- Graph traversal
- Metadata filtering
- Time-aware ranking
- Source-authority ranking
- Symbol-aware code retrieval
- Query expansion
- Reranking

### Code ingestion considerations

Avoid treating a code repository as a collection of arbitrary text chunks.

Prefer:

- AST-aware parsing
- Symbol extraction
- Function and class boundaries
- Import graphs
- Call relationships where feasible
- File-level summaries
- Repository hierarchy
- Commit and blame metadata
- README and documentation links

Start with one or two languages if necessary, such as Python and TypeScript, then expand.

---

## 14. GraphRAG Guidance

GraphRAG should be used only where relationships improve the user experience.

Potential nodes:

- Repository
- Service
- File
- Symbol
- Commit
- Pull request
- Ticket
- Epic
- Document
- Design
- Person
- Team
- Incident
- Requirement

Potential edges:

- implements
- modifies
- depends_on
- references
- discusses
- designed_in
- owned_by
- assigned_to
- introduced_by
- supersedes
- conflicts_with
- documents
- resolves
- blocks
- belongs_to
- affected_by

Do not create model-inferred edges without storing confidence and supporting evidence.

---

## 15. Reliability Requirements

Reliability is a central product requirement, not a later enhancement.

The system should:

- Never invent citations
- Verify that cited artifacts support the associated claim
- Provide source URLs
- Label inference separately from direct evidence
- Detect missing context
- Detect conflicting sources
- Prefer newer information when appropriate, while preserving historical context
- Avoid exposing artifacts the user cannot access
- Log retrieval and generation traces
- Allow evaluation of answer quality
- Support reproducible test cases
- Preserve source timestamps

---

## 16. Evaluation Plan

Evaluation should begin during the MVP.

### Retrieval evaluation

Measure:

- Precision@k
- Recall@k
- Mean reciprocal rank
- Source diversity
- Relationship retrieval accuracy
- Exact-ID retrieval accuracy
- Relevant-file retrieval accuracy

### Answer evaluation

Measure:

- Faithfulness
- Citation correctness
- Citation completeness
- Answer relevance
- Unsupported-claim rate
- Abstention quality
- Conflict-awareness
- Helpfulness for the selected workflow

### Product evaluation

Measure:

- Time to find relevant context
- Percentage of questions resolved without manually opening multiple tools
- User-rated confidence
- Number of useful sources surfaced
- Onboarding-task completion time
- Bug-investigation time
- Feature-context reconstruction time

### Initial evaluation dataset

Create a small benchmark from one or more public repositories.

Each example should include:

- User question
- Expected relevant artifacts
- Expected relationships
- Gold or reference answer
- Unsupported claims to avoid
- Expected abstention behavior where applicable

---

## 17. Security and Privacy

Security should be included in the design from the beginning.

Requirements:

- Encrypt connector tokens
- Do not log raw secrets
- Isolate data by workspace
- Respect source permissions
- Support connector revocation
- Support deletion
- Avoid training on customer data
- Make data-retention behavior explicit
- Record access and sync events
- Apply least-privilege access
- Sanitize content used in prompts
- Defend against prompt injection contained within connected documents
- Treat repository content, tickets, comments, and documents as untrusted input

---

## 18. Prompt-Injection Threat Model

Connected artifacts may contain malicious or misleading instructions.

The system must treat all ingested content as data, not instructions.

Examples of unsafe content:

- A README telling the model to ignore system instructions
- A Jira comment requesting secrets
- A code comment attempting to alter model behavior
- A Slack message containing adversarial prompt text

Mitigations:

- Strong separation between system instructions and retrieved content
- Content sanitization
- Tool allowlists
- Permission checks before retrieval
- No execution of code from retrieved artifacts
- Output validation
- Citation validation
- Adversarial test suite
- Restricted tool privileges

---

## 19. Suggested Technical Architecture

This is a starting point, not a final decision.

### Frontend

- Next.js
- TypeScript
- React
- Component library such as shadcn/ui
- React Query or equivalent
- Interactive source and graph views

### Backend

- Python
- FastAPI
- Pydantic
- Async workers
- REST APIs initially
- WebSockets or server-sent events for ingestion progress if useful

### Primary database

- PostgreSQL

### Vector storage

Options:
- pgvector for a simpler MVP
- Dedicated vector database later if scale requires it

Start with pgvector unless a strong requirement justifies another system.

### Graph storage

Options:
- PostgreSQL relationship tables for MVP
- Neo4j or another graph database later if graph traversal complexity requires it

Avoid introducing a graph database too early unless benchmarks show it is needed.

### Queue / background jobs

Options:
- Redis + Celery
- Redis + RQ
- Temporal
- Cloud-native queue

Choose the simplest reliable system for the MVP.

### Object storage

- S3-compatible storage for large artifacts and raw ingestion payloads

### LLM layer

The system should be model-provider-agnostic where practical.

Create interfaces for:

- generation
- embeddings
- reranking
- structured extraction
- evaluation

Potential providers may include Anthropic, OpenAI, Google, or open models.

### Observability

- Structured logs
- OpenTelemetry
- LLM trace logging
- Retrieval trace logging
- Cost and latency tracking
- Error monitoring

### Deployment

MVP options:
- Docker
- Railway, Render, Fly.io, or AWS
- Managed PostgreSQL
- CI/CD through GitHub Actions

The infrastructure should be appropriate for a serious project but not overengineered solely for appearance.

---

## 20. Non-Functional Requirements

- Secure
- Observable
- Modular
- Testable
- Source-citable
- Provider-agnostic where reasonable
- Connector-extensible
- Incrementally indexable
- Workspace-isolated
- Responsive for common queries
- Resilient to partial connector failures
- Able to communicate ingestion and answer uncertainty
- Designed for gradual scaling

---

## 21. Non-Goals for the MVP

Do not attempt to build:

- Every connector
- A full enterprise permission-sync engine
- Real-time ingestion for every platform
- A complete IDE extension
- Autonomous code modification
- Autonomous production deployment
- A general-purpose enterprise assistant
- A replacement for GitHub, Jira, Figma, or Slack
- Perfect repository understanding for every programming language
- A fully autonomous incident-response agent
- A polished startup-scale billing system

---

## 22. Product Roadmap

### Phase 0 — Product definition

- Finalize PRD
- Identify primary persona
- Select MVP workflow
- Select first connectors
- Write user journeys
- Define success metrics
- Define evaluation dataset

### Phase 1 — Repository intelligence

- GitHub authentication
- Repository selection
- Repository ingestion
- Code-aware chunking
- Basic repository search
- Evidence-backed repository Q&A
- Source citations

### Phase 2 — Cross-platform context

- Jira authentication
- Jira ingestion
- Common artifact model
- Ticket-to-PR and ticket-to-code relationships
- “Trace a ticket” workflow
- Hybrid and graph-aware retrieval

### Phase 3 — Reliability

- Evaluation harness
- Prompt-injection tests
- Citation validation
- Conflict detection
- Abstention behavior
- Retrieval observability

### Phase 4 — Additional connector

Choose one:
- Figma
- Notion
- Slack
- Linear

Figma is especially compelling because it introduces multimodal and design-to-code context.

### Phase 5 — Proactive intelligence

- Stale documentation detection
- Unimplemented requirement detection
- Relevant-context recommendations
- Change-impact summaries
- Onboarding paths

---

## 23. Important Design Questions

Claude should not silently decide these without documenting the reasoning:

1. What is the narrowest MVP user problem?
2. Who is the first primary user?
3. Which two connectors should be implemented first?
4. What is the canonical artifact model?
5. Which relationships can be derived deterministically?
6. Which relationships may be inferred by a model?
7. How will permissions be represented?
8. How will source freshness be handled?
9. How will code be parsed and indexed?
10. How will citation correctness be evaluated?
11. What should happen when sources conflict?
12. What should happen when evidence is insufficient?
13. What belongs in PostgreSQL versus object storage?
14. Is a graph database justified for the MVP?
15. How will connector failures be retried?
16. How will incremental syncing work?
17. What is the first public evaluation dataset?
18. Which parts of the architecture should remain provider-agnostic?

---

## 24. Spec-Driven Development Workflow

All development must follow a specification-driven process.

Required sequence:

1. Product requirement
2. Clarifying questions
3. Written specification
4. Acceptance criteria
5. Architecture decision
6. Implementation plan
7. Task breakdown
8. Implementation
9. Tests
10. Validation against acceptance criteria
11. Documentation update

Claude should not begin writing production code until the relevant specification and acceptance criteria are approved.

### Required documents

Recommended repository structure:

```text
/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── vision.md
│   ├── prd.md
│   ├── architecture.md
│   ├── evaluation.md
│   ├── security.md
│   ├── data-model.md
│   ├── api.md
│   ├── roadmap.md
│   └── decisions/
│       ├── ADR-001-*.md
│       └── ADR-002-*.md
├── specs/
│   ├── 001-workspace-auth/
│   │   ├── spec.md
│   │   ├── plan.md
│   │   └── tasks.md
│   └── 002-github-ingestion/
├── backend/
├── frontend/
├── workers/
├── packages/
├── tests/
└── infra/
```

### Definition of ready

A feature is ready for implementation when:

- The user problem is defined
- Scope and non-scope are explicit
- Functional requirements are written
- Acceptance criteria are testable
- Dependencies are identified
- Security implications are considered
- Evaluation or validation method is defined
- Open questions are resolved or explicitly deferred

### Definition of done

A feature is done when:

- Acceptance criteria pass
- Unit and integration tests pass
- Relevant evaluation tests pass
- Documentation is updated
- Observability is included
- Error states are handled
- Security considerations are addressed
- No unsupported assumptions were introduced
- The implementation matches the approved specification

---

## 25. Development Principles

Claude should follow these principles throughout the project:

1. Do not overengineer the MVP.
2. Do not build features simply because they sound impressive.
3. Every feature must connect to a real user problem.
4. Reliability is part of product quality.
5. Retrieved content is untrusted input.
6. Every generated answer should be evidence-backed where possible.
7. Use deterministic methods before model inference when appropriate.
8. Clearly label model inference.
9. Preserve source metadata and timestamps.
10. Prefer modular connector interfaces.
11. Write tests before or alongside implementation.
12. Document architecture decisions.
13. Ask clarifying questions when product intent is ambiguous.
14. Do not silently change approved requirements.
15. Keep the system understandable enough for one developer to maintain.
16. Use production-quality conventions without pretending the project already has enterprise scale.
17. Optimize first for a credible, useful MVP.
18. Build evaluation into each AI feature.
19. Do not add a chat interface as a substitute for product design.
20. Explain trade-offs before making high-impact technical decisions.

---

## 26. Expected Collaboration Style

Claude should behave like a thoughtful technical cofounder and senior engineer, not an autocomplete tool.

Claude should:

- Challenge unclear assumptions
- Identify missing requirements
- Explain trade-offs
- Avoid premature implementation
- Produce structured specs
- Keep a list of open questions
- Create ADRs for significant decisions
- Trace implementation tasks back to requirements
- Verify completed work against acceptance criteria
- Call out unnecessary complexity
- Avoid inventing user needs
- Preserve consistency across documents
- Update documentation as decisions change

Claude should not:

- Generate the entire application in one pass
- Select technologies only because they are trendy
- create fake metrics
- Claim a feature is production-ready without validation
- Add unsupported functionality
- Ignore security and permissions
- Treat all connected content as trustworthy
- Skip evaluation for AI outputs

---

## 27. First Assignment for Claude

Do not begin implementation.

First:

1. Read this entire handoff.
2. Restate the product in your own words.
3. Identify assumptions, contradictions, and missing information.
4. Ask the highest-leverage product questions required to finalize the PRD.
5. Recommend the narrowest credible MVP.
6. Recommend the first primary persona.
7. Compare GitHub + Jira versus GitHub + Notion as the first connector pair.
8. Propose measurable success criteria.
9. Propose a phased development plan.
10. Create or revise:
   - `docs/vision.md`
   - `docs/prd.md`
   - `docs/roadmap.md`
11. Do not create implementation code until the PRD is reviewed and approved.

---

## 28. Initial Prompt to Give Claude Code

Use the following prompt after placing this file in the repository:

> You are helping me design and build ContextOS using a strict specification-driven development workflow. Read `CONTEXT_OS_CLAUDE_HANDOFF.md` completely before taking action. Treat it as the current source of project context, but do not assume every detail is finalized.  
>
> Your first task is product definition, not coding. Restate your understanding of the product, identify the highest-risk assumptions and missing decisions, and ask me the most important clarifying questions needed to finalize the MVP PRD. Then propose a narrow MVP, primary persona, first workflow, initial connector pair, measurable success criteria, and a phased implementation roadmap.  
>
> Do not generate application code yet. Do not silently choose technologies or expand scope. Every recommendation must explain the user problem it addresses and the trade-offs involved. All future work must follow: requirement → specification → acceptance criteria → architecture decision → implementation plan → tasks → code → tests → validation.

---

## 29. Short Project Pitch

ContextOS is an AI-native engineering context engine that connects code, tickets, designs, documentation, conversations, and operational data so software teams can understand how their systems work and why decisions were made. Instead of forcing engineers to search across disconnected tools, ContextOS reconstructs the relationships among requirements, designs, discussions, pull requests, commits, and source code, then delivers task-specific, evidence-backed context for onboarding, feature development, debugging, code review, and incident investigation.

---

## 30. Core Story for Interviews

The project originated from repeatedly entering unfamiliar technical environments and realizing that writing code was not initially the hardest part. The harder problem was building enough context to make responsible changes. Product decisions lived in one tool, requirements in another, implementation details in code, and historical reasoning in conversations. Existing AI coding tools could generate solutions before the user understood whether those solutions belonged in the system.

ContextOS explores a different role for AI: helping engineers build an accurate, evidence-backed mental model of a system before they act.
