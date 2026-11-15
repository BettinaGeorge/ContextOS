# ADR-008: Escape retrieved content in the evidence block

Status: Accepted (2026-11-15; validated in `specs/003-reliability-hardening/validation.md`).

## Context

Retrieved content and several item attributes (identifier, type, origin, source address) are interpolated into an `<evidence>` block with no escaping. The fixed system prompt is kept separate from retrieved content and that is tested, but the tests only check where content lands. A document containing the closing evidence tag can end the section early, and a crafted address can inject extra attributes. On a replica of the current formatting code, one real item produced two evidence sections with injected text outside the data block. This is the attack class Constitution Principle III exists to prevent.

## Decision

- Escape every attribute value with `html.escape(value, quote=True)` and every item body with `html.escape(value, quote=False)` before it enters the block.
- Add one sentence to the fixed system prompt: evidence is escaped, `&lt;` means a literal `<`, and quoted evidence should use the original characters.
- Add an adversarial test set of at least eight break-out patterns covering each field.

## Consequences

- A forged `</evidence>`, `<item ...>` or attribute can no longer exist as markup.
- Code containing `<`, `>` or `&` reaches the model in escaped form, which slightly increases the chance of the model echoing escaped text; the prompt sentence mitigates this and manual validation should look for it.
- The existing prompt-isolation tests pass unchanged: their strings contain no special characters.
- Citation validation is unchanged and still the final check on what is cited.

## Alternatives considered

- **Per-request random boundary token**: forged item lookalikes would still appear inside content and rely on the model ignoring them.
- **Escape only the delimiter strings**: a denylist is easy to bypass with case, spacing or partial tags.
- **Strip angle brackets from content**: destroys code and markup evidence.
