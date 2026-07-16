# AI Workflow Rules

## Approach

Build incrementally using a spec-driven workflow. The `context/` files define
what to build, how it fits together, and the current state. Always implement
against the current unit spec in `context/specs/` — do not infer or invent
behavior from scratch. Read the six context files (in the order listed in
`CLAUDE.md`) before writing code or making an architectural decision.

## Scoping Rules

- Work on **one unit at a time**, in the order set by
  `context/specs/00-build-plan.md`.
- Do not build on something that doesn't exist yet — respect the unit
  dependencies.
- Do not combine the two system boundaries (`firmware/` and `phone/`) in a single
  step unless the unit spec explicitly spans both.
- Prefer small, end-to-end-verifiable increments over large speculative changes.

## When to Split Work

Split a step if it combines:

- Firmware changes and phone/server changes that could each be verified
  independently.
- Localization changes and OCR-engine changes (localization is CV; OCR is the
  spiked engine — keep them separable).
- Any behavior not clearly defined in the context files or the current spec.

If a change can't be verified end to end quickly (flash + press + see the
dashboard update, or `curl` + see the response), the scope is too broad — split
it.

## Handling Missing Requirements

- Do not invent behavior not defined in the context files or the current spec.
- If the ESP32↔phone contract is ambiguous, resolve it in
  `interface-context.md` **before** implementing either side — both sides read
  from that one definition.
- If a requirement is missing, add it as an open question in
  `progress-tracker.md` before continuing.

## Protected Files / Boundaries

Do not modify unless explicitly instructed:

- The fixed AI-Thinker camera pin mapping in `pins.h` (the OV2640 data/sync pins
  are hardware-fixed).
- `firmware/secrets.h` contents (developer-local; only `secrets.h.example` is
  edited in the repo).
- The `POST /upload` contract shape in `interface-context.md` — changing the wire
  format means updating that file first, then both sides together.

## Keeping Docs in Sync

Update the relevant context file whenever implementation changes:

- System architecture or the boundary between firmware and phone.
- The HTTP contract or the Malaysian plate pattern (`interface-context.md`).
- Data/storage decisions (what's saved, where, gitignore).
- Code conventions or the chosen OCR engine (`code-standards.md`).
- Feature scope (`project-overview.md`).

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope.
2. No invariant in `architecture.md` was violated — in particular: pins only in
   `pins.h`, no ISR work, no secrets/plate data in git, no cloud dependency, no
   confident report of an invalid plate.
3. `progress-tracker.md` reflects the completed work and any new decisions.
4. The unit's own "Verify when done" checklist passes (flash/run succeeds cleanly,
   no errors/warnings).
