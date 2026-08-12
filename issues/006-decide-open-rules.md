## Parent PRD

`issues/prd.md`

## What to build

**HITL.** Not code — five decisions, made deliberately and written down, then encoded in the Comparator.

These are the judgment calls in the system. They are the thing a reviewer will probe, and they should be answered on purpose rather than defaulted at 1am. Each is cheap to change afterwards because all five live inside one pure function.

**The five:**

1. **Rounding tolerance.** A deck stating `$4.2M` against `4,183,204` is not a defect. Relative band, absolute band, or scale-dependent? What about `$4.2M` against `4,249,000`?
2. **Confidence threshold for surfacing a flag.** Is a missed defect worse than a false alarm? The PRD's working assumption is yes — an analyst re-checks a false alarm in seconds but never sees a miss. Confirm or reject.
3. **Whether `NO_EVIDENCE` is surfaced or only logged.** Data rooms are legitimately incomplete, and a wall of `NO_EVIDENCE` would drown the real findings.
4. **`NO_SOURCE` behaviour.** Confirm that "no filing covers this period" is reported separately from "looked and found nothing."
5. **The `BASIS_MISMATCH` detection rule.** How is "different accounting basis" distinguished from "wrong number"? This is the hardest judgment in the system and its most valuable output.

Record the reasoning, not just the answer. The *why* is what makes the ceilings section credible.

## Acceptance criteria

- [ ] All five decisions made and written into the PRD's open-questions section, replacing the questions
- [ ] Each carries a one-line rationale
- [ ] Tolerance encoded in the Comparator as a named constant, not scattered magic numbers
- [ ] `BASIS_MISMATCH` rule expressed concretely enough to write tests against
- [ ] Every decision is changeable in one place

## Blocked by

- Blocked by `issues/005-decision-engine.md`

## User stories addressed

- User story 13
- User story 21
- User story 24
- User story 25
