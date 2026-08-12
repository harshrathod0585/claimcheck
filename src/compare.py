"""(Claim, Evidence) -> Verdict. All arithmetic happens here, in Python."""

from __future__ import annotations

import math
from typing import Optional

from .models import (Basis, Claim, Evidence, Operation, Quantity, Status,
                     Unit, Verdict)
from .normalize import significant_figures

# --- tunable rules (issue 006 owns these) ------------------------------------

#: Half-width of the rounding band, in units of the last significant digit of
#: the claim as written. 0.5 == "anything that rounds to the claimed figure".
ROUNDING_BAND_ULPS = 0.5

#: Fallback relative band when the claim has no parseable written form.
DEFAULT_RELATIVE_BAND = 0.005

#: Ratio at or beyond which a difference is reported as a scale error rather
#: than an ordinary disagreement (millions stated as billions).
SCALE_MISMATCH_RATIO = 9.5

#: Which basis the "actual" is taken from when the evidence mixes bases.
#: Everything else becomes an alternate basis candidate.
PRIMARY_BASIS_ORDER = (Basis.GAAP, Basis.UNKNOWN)


def numeric_band(claim_value: float, raw: str) -> float:
    """Absolute tolerance around a claimed figure, from its significant figures.

    '$4.2M' is 2 sig figs -> band of +/-0.05M, so anything rounding to 4.2
    passes and 4.9 does not.
    """
    sig = significant_figures(raw)
    if not sig or claim_value == 0:
        return abs(claim_value) * DEFAULT_RELATIVE_BAND
    exponent = math.floor(math.log10(abs(claim_value)))
    ulp = 10 ** (exponent - (sig - 1))
    return ulp * ROUNDING_BAND_ULPS


def within_tolerance(claimed: Quantity, actual: Quantity) -> tuple[bool, str]:
    """Unit, period and scale are checked BEFORE the numeric band, so that
    $4.2M and $4.2B never compare equal on their digits alone."""
    if claimed.unit != actual.unit:
        return False, f"unit mismatch: {claimed.unit.value} vs {actual.unit.value}"

    if claimed.period is not None and actual.period is not None:
        if not claimed.period.matches(actual.period):
            return False, (f"period mismatch: claim {claimed.period.label or claimed.period.key()} "
                           f"vs evidence {actual.period.label or actual.period.key()}")

    c, a = claimed.base_value, actual.base_value
    if c and a:
        ratio = abs(c) / abs(a)
        if ratio >= SCALE_MISMATCH_RATIO or ratio <= 1 / SCALE_MISMATCH_RATIO:
            return False, f"scale mismatch: {c:,.6g} vs {a:,.6g}"

    band = numeric_band(claimed.value, claimed.raw) * claimed.scale
    if abs(c - a) <= band:
        return True, ""
    return False, f"outside band: {c:,.6g} vs {a:,.6g} (+/-{band:,.6g})"


def compute(operation: Operation, quantities: list[Quantity]) -> Optional[Quantity]:
    """Derive the actual figure from retrieved primitives. Never a model."""
    if not quantities:
        return None
    first = quantities[0]

    if operation is Operation.ABSOLUTE:
        return first

    if len(quantities) < 2:
        return None
    a, b = quantities[0].base_value, quantities[1].base_value
    if b == 0:
        return None

    if operation is Operation.GROWTH:
        value = (a - b) / b * 100.0
    elif operation is Operation.MARGIN:
        value = a / b * 100.0
    else:
        return None

    return Quantity(value=value, unit=Unit.PERCENT, scale=1.0,
                    period=first.period, basis=first.basis, raw=f"{value:g}")


def _groups(quantities: list[Quantity]) -> dict[Basis, list[Quantity]]:
    out: dict[Basis, list[Quantity]] = {}
    for q in quantities:
        out.setdefault(q.basis, []).append(q)
    return out


def _primary_basis(groups: dict[Basis, list[Quantity]]) -> Basis:
    for basis in PRIMARY_BASIS_ORDER:
        if basis in groups:
            return basis
    return next(iter(groups))


def compare(claim: Claim, evidence: Evidence) -> Verdict:
    """The decision order is the specification. Do not reorder."""
    # 1. no document covered the claim's period
    if not evidence.covers(claim.period):
        return Verdict(Status.NO_SOURCE, claim=claim, claimed=claim.value.base_value,
                       claimed_basis=claim.basis, evidence=evidence,
                       reason="no document covers the claim's period")

    # 2. the agent found no quantities
    if not evidence.quantities:
        return Verdict(Status.NO_EVIDENCE, claim=claim, claimed=claim.value.base_value,
                       claimed_basis=claim.basis, evidence=evidence,
                       reason="no quantities retrieved")

    groups = _groups(evidence.quantities)
    primary = _primary_basis(groups)

    # 3. actual = compute(...)
    actual = compute(claim.operation, groups[primary])
    if actual is None:
        return Verdict(Status.NO_EVIDENCE, claim=claim, claimed=claim.value.base_value,
                       claimed_basis=claim.basis, evidence=evidence,
                       reason=f"not enough quantities to compute {claim.operation.value}")

    # 4. within tolerance
    ok, reason = within_tolerance(claim.value, actual)
    if ok:
        return Verdict(Status.SUPPORTED, claim=claim, claimed=claim.value.base_value,
                       actual=actual.base_value, claimed_basis=claim.basis,
                       actual_basis=actual.basis, evidence=evidence)

    # 5. matches any alternate basis within tolerance
    for basis, qs in groups.items():
        if basis is primary:
            continue
        alt = compute(claim.operation, qs)
        if alt is None:
            continue
        alt_ok, _ = within_tolerance(claim.value, alt)
        if alt_ok:
            return Verdict(Status.BASIS_MISMATCH, claim=claim,
                           claimed=claim.value.base_value, actual=actual.base_value,
                           claimed_basis=claim.basis, actual_basis=basis,
                           evidence=evidence,
                           reason=(f"claim matches {basis.value} "
                                   f"({alt.base_value:,.6g}) but not "
                                   f"{primary.value} ({actual.base_value:,.6g})"))

    # 6. otherwise
    return Verdict(Status.CONTRADICTED, claim=claim, claimed=claim.value.base_value,
                   actual=actual.base_value, claimed_basis=claim.basis,
                   actual_basis=actual.basis, evidence=evidence, reason=reason)
