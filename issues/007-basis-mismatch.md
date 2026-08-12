## Parent PRD

`issues/prd.md`

## What to build

`BASIS_MISMATCH` as a first-class verdict. The differentiated part of the system.

A deck reporting ARR of $3.0B against a filing's GAAP revenue of $2.8B is not lying — it is measuring differently. Flagging that as a contradiction is the naive failure and the fastest way to lose an analyst's trust. Identifying it correctly is the senior one, and it is the most common real discrepancy in genuine filings.

Two halves. The agent must find **both** figures — the GAAP number in the financial statements and the non-GAAP reconciliation, which typically sits in a different Item entirely. The Comparator must then apply the rule from `issues/006` to distinguish a basis difference from a wrong number.

When the agent's first pass yields a mismatch that smells like a basis gap, it should go looking for the reconciliation rather than reporting a contradiction.

## Acceptance criteria

- [ ] `BASIS_MISMATCH` emitted when both figures are found, both are correct, and the bases differ
- [ ] Both bases are named explicitly in the output, e.g. `claimed: ARR`, `actual: GAAP revenue`
- [ ] The agent retrieves the non-GAAP reconciliation section alongside the statement section when a basis gap is suspected
- [ ] A deck ARR figure against a filing GAAP revenue figure produces `BASIS_MISMATCH`, not `CONTRADICTED`
- [ ] A genuinely wrong number that matches no basis produces `CONTRADICTED`, not `BASIS_MISMATCH`
- [ ] Basis mismatches are counted separately in the run summary
- [ ] Test cases cover both directions, including the near-miss where a wrong figure resembles a different basis

## Blocked by

- Blocked by `issues/006-decide-open-rules.md`

## User stories addressed

- User story 13
- User story 24
- User story 25
- User story 26
