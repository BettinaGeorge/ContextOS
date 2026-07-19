# ADR-002: Switch LLM provider from Anthropic Claude to Groq

Status: Accepted.

## Context

ADR-001 chose Anthropic Claude for generation, accepting it as the one layer of the stack with real (if small and capped) ongoing cost — the reasoning at the time was that a hard $8/month spend limit kept it safely inside the project's $10 budget ceiling, and pay-per-use (not a subscription) satisfied "no recurring cost."

That reasoning assumed a small capped bill was an acceptable trade. On review, it isn't — the actual constraint is **$0, no payment method on file at all**, not "a small bill under a cap." Anthropic's API requires a payment method before issuing API access, regardless of how low the spend cap is set. That alone disqualifies it under the real constraint.

This ADR only revisits the LLM provider. Every other row in ADR-001 (Supabase, Vercel, Render, the Postgres-backed job table, Voyage for embeddings, etc.) is unaffected and still stands.

## Decision

Switch to **Groq** for generation.

| Aspect | Choice | Why |
|---|---|---|
| Provider | Groq (hosted inference of open-weight models) | Genuinely free tier, no payment method required to obtain an API key — the only option evaluated that actually satisfies the $0 constraint without a data-use trade-off (see Alternatives). |
| Model | `llama-3.3-70b-versatile` (default), `llama-3.1-8b-instant` (available as a faster fallback) | Llama 3.3 70B is competitive for structured instruction-following — the exact `[cite:ARTIFACT_ID]` marker format `answer_svc`'s citation validation depends on. **Verified against the real API**, not just assumed: a live call correctly used the `[cite:ID]` format on the first try, and a full `answer_svc` run (real Groq call, real DB-backed evidence) produced a correctly-parsed citation matching the actual retrieved artifact, with the model's prose appropriately hedged ("possibly," "may not be directly related") because the evidence was labeled `inferred` rather than `explicit`. |
| Integration | Groq's Python SDK, OpenAI-compatible request/response shape | Smaller, lower-risk migration than a bespoke SDK would have been — the only structural change from the Claude implementation was moving the system prompt into the `messages` list (`role: "system"`) instead of a separate `system=` parameter. Evidence-block construction, the citation-marker instructions, and the untrusted-content isolation boundary (Constitution Principle III) carried over unchanged. |

Renamed `backend/src/llm/claude_client.py` → `groq_client.py`, `ClaudeClient` → `GroqClient`, `ANTHROPIC_API_KEY` → `GROQ_API_KEY` across `.env.example`, `backend/.env`, `Settings` (`config.py`), and all call sites/tests.

## Consequences

- LLM generation is now genuinely $0, closing the one remaining real-cost line item from ADR-001. Only Voyage AI (embeddings) remains a paid-tier dependency, unchanged by this decision.
- Groq's free tier is rate-limited (requests/tokens per minute and per day). Not a problem at this project's current volume (a handful of questions during manual validation), but worth watching if usage grows — there's no spend cap to fall back on the way there was with Anthropic, because there's no billing relationship at all. A rate-limit error would surface as a failed request, not a cost.
- No multi-provider abstraction was introduced to make this swap easier — per Constitution Principle V (narrowest credible scope) and ADR-001's original reasoning, building one before a second provider was actually needed would have been premature. This migration confirms that call was fine: the actual code change was small (one file, a handful of call sites) specifically because `answer_svc` already depended on a narrow interface (`generate_grounded_answer(question, evidence) -> str`), not because a provider-abstraction layer existed.
- Model choice (Llama 3.3 70B via Groq) is a real quality trade against Claude Sonnet — acceptable here because the task (grounded generation with a narrow, mechanically-checked citation format) doesn't require frontier-model reasoning, and because the safety property that matters most (never presenting an unvalidated citation) is enforced in `answer_svc`'s own code, not trusted to the model regardless of which one is used.

## Alternatives considered

- **Google Gemini free tier** — genuinely free, no card, and likely higher raw model quality than Groq's hosted open models. Rejected specifically because of its data-use terms: free-tier usage typically permits Google to use submitted content to improve their models, which directly conflicts with this project's own stated principle (handoff §17: "avoid training on customer data") — we'd be sending users' ingested repo/Notion content through exactly the kind of pipeline the project argues against. Worth reconsidering only if Groq's rate limits become a real blocker and no other option is available.
- **Local inference via Ollama** — genuinely $0 forever, strongest possible privacy story (nothing leaves the machine), and actually the best philosophical fit for the project's own untrusted-content-isolation principle. Rejected due to real reliability risk: models small enough to run well on typical laptop hardware (7-8B parameters) are noticeably less consistent at strict instruction-following than Groq's hosted 70B model, and `answer_svc`'s citation-validation logic depends on that consistency. A larger local model (70B-class) would close this gap but needs more RAM/compute than is safe to assume is available. Revisit if Groq itself becomes unworkable.
- **OpenAI (gpt-4o-mini)** — rejected outright: requires a payment method the same as Anthropic did, so it doesn't satisfy the actual constraint any better.
