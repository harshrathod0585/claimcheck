## Parent PRD

`issues/prd.md`

## What to build

The spot check. Not an evaluation harness — one script, one afternoon, three numbers.

Take the real deck and plant roughly fifteen defects, one or two per category: inflated figure, wrong growth rate, fabricated customer, wrong margin, period swap, unit error. Run the system. Count by hand.

Report three things in the README: how many were caught, which were missed and why, and how many correct claims were falsely flagged.

Deliberately **not** precision, recall, or F1. Fifteen hand-counted cases cannot support statistical framing, and dressing them in it is exactly the overclaiming this project should avoid. "Caught 13 of 15, here are the 2 it missed" is more credible than a decimal.

The misses matter more than the catches. Knowing why your own system failed is the signal.

## Acceptance criteria

- [ ] Seeder script injects ~15 defects into the real deck, covering all six categories
- [ ] Ground truth recorded per injected defect
- [ ] Run produces a caught/missed count against that ground truth
- [ ] Each miss is listed with a one-line explanation of why it was missed
- [ ] Correct claims that were falsely flagged are counted and reported
- [ ] No precision, recall, or F1 vocabulary anywhere in the output or README
- [ ] Results are regenerable by running one command

## Blocked by

- Blocked by `issues/007-basis-mismatch.md`

## User stories addressed

- User story 35
- User story 36
- User story 37
- User story 38
- User story 39
