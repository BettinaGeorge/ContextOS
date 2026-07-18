# ContextOS — Vision

## The problem

Engineers don't struggle to write code. They struggle to know *what code to write* and *why*, because the context that justifies a change is scattered across tools: requirements live in a docs tool, decisions live in comment threads, implementation lives in a repo, and the connections between them live in someone's memory. Every new engineer, every engineer switching teams, and every engineer touching unfamiliar code has to manually reconstruct that picture before they can make a responsible change.

This problem is not a search problem. The information usually *exists*. The missing piece is the relationships between artifacts — which doc justifies which PR, which ticket introduced which behavior, which decision is still current versus stale.

## What ContextOS is

ContextOS is a context-reconstruction engine for software teams. It connects the tools a team already uses — starting with GitHub and Notion — and answers questions about how a codebase works, why something was built the way it was, and what's related to a given task, with **evidence-backed, citation-traceable answers**.

It does this by:
1. Normalizing artifacts from connected tools into a common model.
2. Extracting relationships between those artifacts — deterministically where possible (explicit IDs, links, references), and only inferring where deterministic linking isn't available.
3. Answering task-specific questions grounded only in retrieved evidence, distinguishing fact from inference, and saying so explicitly when evidence is insufficient.

## What ContextOS is not

- Not a generic "chat with your docs" RAG wrapper.
- Not a code-completion or autocomplete tool.
- Not an enterprise search clone that returns a list of loosely related documents.
- Not a chatbot that answers confidently regardless of whether it has evidence.

## Core principle

**AI should help a user build an accurate mental model before they act** — not hand them an answer to blindly trust. Every claim ContextOS makes should be traceable to a source, and every gap in evidence should be visible rather than papered over.

## Origin

This product comes directly from lived experience: repeatedly entering unfamiliar codebases (as a two-time SWE intern, as a student contributor, as a teaching assistant helping other engineers debug) and finding that the hard part wasn't writing code — it was reconstructing enough context to know which code to write. ContextOS is built to solve that problem for the next engineer who hits it.

## Who it's for first

The first user is an **engineer switching teams or joining an existing one** — someone who needs to build a working mental model of unfamiliar code and its surrounding context quickly, without waiting on a teammate to explain it live. See `docs/prd.md` for the full persona and workflow definition.

## Differentiation, long-term

1. Cross-platform engineering context (not single-source)
2. Relationship-aware retrieval, not flat document search
3. Task-specific context assembly, not generic Q&A
4. Evidence-backed answers with citation validation
5. Explicit uncertainty and conflict detection
6. Code-aware and (eventually) design-aware understanding
7. Access-control-aware retrieval, respecting source permissions

Full detail on scope, requirements, and what's deliberately deferred lives in `docs/prd.md`. Phasing lives in `docs/roadmap.md`.
