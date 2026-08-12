## Parent PRD

`issues/prd.md`

## What to build

The decision engine — Normalizer and Comparator. **No model calls anywhere in this slice.**

The Normalizer parses a figure as it appears in a document into a structured quantity: value, unit, scale, period, and accounting basis. `$4.2M`, `4,183,204`, `(1,978)`, `72%`, `FY2024`, `Q4 2023` all become comparable.

The Comparator takes a claim and the quantities the agent retrieved and produces a verdict. All arithmetic happens here — growth rates, margins, ratios — computed from retrieved primitives. Tolerance, period matching, and unit scaling live here.

This is the deepest module in the system and where the test suite concentrates. Both are pure functions: no I/O, no network, no model, no API key required to test them exhaustively.

## Acceptance criteria

- [ ] Normalizer parses: `$4.2M`, `4,183,204`, `(1,978)` as negative, `72%`, `140 bps`, thousands-vs-millions table units
- [ ] Normalizer parses periods: `FY2024`, `Q4 2023`, `three months ended October 31, 2023`
- [ ] Comparator computes growth rates, margins, and ratios in Python from retrieved values
- [ ] A deck's `$4.2M` against a filing's `4,183,204` resolves as agreement, not a defect
- [ ] An FY2023 figure labelled FY2024 is caught as a period mismatch
- [ ] Millions stated as billions is caught as a unit error, not missed because the digits match
- [ ] Verdicts emitted: `SUPPORTED`, `CONTRADICTED`, `NO_EVIDENCE`, `NO_SOURCE`
- [ ] `NO_SOURCE` fires when no document covers the claim's period — distinct from having looked and found nothing
- [ ] Both modules are pure functions with no I/O and no model calls
- [ ] Table-driven tests cover every rule above and run with no API key and no network

## Blocked by

- Blocked by `issues/004-verification-agent.md`

## User stories addressed

- User story 14
- User story 21
- User story 22
- User story 23
