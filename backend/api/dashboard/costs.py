"""What the service costs the operator (/api/admin/costs): each call priced
in rupees, the month's total, and the price list behind it. Admins only.

Money is never stored: each call's exact usage is (models.Usage), priced
here with the price list the operator edits on the Prices screen
(clinic_agent/costs.py). Nothing here is patient data: usage rows hold
counts, never words.
"""

# No `from __future__ import annotations` here: _routes types each body
# with a variable, which FastAPI must see as the class itself.

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from api.dashboard import convert, schemas
from api.dashboard.access import admin, staff_errors
from clinic_agent import costs
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])

PART_LABELS = {
    "listening": "Listening (speech to text)",
    "thinking": "Thinking (language model)",
    "speaking": "Speaking (text to speech)",
    "call_line": "Call line (LiveKit)",
    "other": "Other (Hindi name suggestions)",
}
VENDOR_LABELS = {"sarvam": "Sarvam", "elevenlabs": "ElevenLabs", "openai": "OpenAI", "livekit": "LiveKit"}
LANGUAGE_LABELS = {"en": "English", "hi": "Hindi", "": "Other costs"}
TOP_CALLS = 100


def book(s) -> costs.PriceBook:
    return costs.PriceBook(repo.cost_rows(s, "prices"), repo.cost_rows(s, "rates"))


def _price_text(price) -> str:
    sign = "₹" if price.currency == "INR" else "$"
    return f"{sign}{price.amount:g} per {costs.per_text(price.per, price.unit)}"


def _lines(b: costs.PriceBook, usage) -> list[schemas.CostLine]:
    out = []
    for u in usage:
        p = b.priced(u)
        price = b.price(u.provider, u.model, u.unit, u.at.date())
        out.append(schemas.CostLine(
            part=u.part, provider=u.provider, model=u.model, unit=u.unit,
            unit_label=costs.UNITS.get(u.unit, u.unit), quantity=u.quantity, rupees=p.rupees,
            price=_price_text(price) if price else "", missing=p.missing,
        ))
    return out


def call_cost(b: costs.PriceBook, usage) -> schemas.CallCost:
    """One call's usage (all rows share the call), priced."""
    first = usage[0]
    lines = _lines(b, usage)
    parts: dict[str, float] = defaultdict(float)
    for line in lines:
        parts[line.part] += line.rupees or 0
    return schemas.CallCost(
        call_id=first.call_id, clinic_id=first.clinic_id, clinic_name=first.clinic_name,
        started_at=convert.utc(first.at), language=first.language, test=first.test,
        rupees=sum(parts.values()), complete=all(not line.missing for line in lines),
        parts=dict(parts), lines=lines,
    )


def cost_of_call(s, call_id: int) -> schemas.CallCost | None:
    """For the call's trace page; None for a call from before costs were tracked."""
    usage = repo.usage_for_calls(s, [call_id])
    return call_cost(book(s), usage) if usage else None


# ---------- the month ----------

@router.get("/costs", response_model=schemas.CostMonth)
def month(request: Request, month: str | None = None):
    now = utc_now()
    name = month or f"{now:%Y-%m}"
    with staff_errors(), request.app.state.sessions() as s:
        try:
            start, end = costs.month_bounds(name)
        except ValueError:
            raise ValueError("Month must look like 2026-10.") from None
        b = book(s)
        usage = repo.usage_between(s, start, end)
        m = costs.month(b, name, usage, repo.cost_rows(s, "allowances"), repo.cost_rows(s, "fixed"))
        bills = [r for r in repo.cost_rows(s, "bills") if r.month == name]
        months = _months(s, name)
        tracked = repo.first_usage_at(s)

    by_call: dict[object, list] = defaultdict(list)
    for u in usage:
        if u.source == "call":
            # An erased or purged call keeps its usage: grouped by its row ids' call, else alone.
            by_call[u.call_id if u.call_id is not None else ("gone", u.clinic_id, u.at)].append(u)
    calls = [call_cost(b, rows) for rows in by_call.values()]
    patient_calls = [c for c in calls if not c.test]

    def slices(key, labels) -> list[schemas.CostSlice]:
        rupees: dict[str, float] = defaultdict(float)
        counted: dict[str, set] = defaultdict(set)
        for p in m.priced:
            k = key(p.usage)
            rupees[k] += p.rupees or 0
            if p.usage.source == "call":
                counted[k].add(p.usage.call_id if p.usage.call_id is not None else ("gone", p.usage.clinic_id, p.usage.at))
        return sorted(
            (schemas.CostSlice(key=k, label=labels(k), rupees=v, calls=len(counted[k])) for k, v in rupees.items()),
            key=lambda x: -x.rupees,
        )

    days: dict[date, float] = defaultdict(float)
    for p in m.priced:
        days[p.usage.at.date()] += p.rupees or 0

    return schemas.CostMonth(
        month=name, months=months, tracked_since=convert.utc(tracked),
        usage_rupees=m.usage_rupees, free_rupees=m.free_rupees, fixed_rupees=m.fixed_rupees,
        to_pay_rupees=m.to_pay, calls=len(patient_calls), test_calls=len(calls) - len(patient_calls),
        per_call_rupees=(sum(c.rupees for c in calls) / len(calls)) if calls else None,
        other_rupees=sum(p.rupees or 0 for p in m.priced if p.usage.source != "call"),
        by_language=slices(lambda u: u.language, lambda k: LANGUAGE_LABELS.get(k, k)),
        by_part=slices(lambda u: u.part, lambda k: PART_LABELS.get(k, k)),
        by_vendor=slices(lambda u: u.provider, lambda k: VENDOR_LABELS.get(k, k)),
        by_clinic=slices(lambda u: u.clinic_name or "(no clinic)", lambda k: k),
        by_day=[schemas.CostDay(day=d, rupees=r) for d, r in sorted(days.items())],
        free=[schemas.FreeUse(provider=f.provider, unit_label=costs.UNITS.get(f.unit, f.unit),
                              allowance=f.allowance, used=f.used, rupees=f.rupees) for f in m.free],
        fixed=[schemas.FixedUse(name=f.name, provider=f.provider, rupees=r) for f, r in m.fixed],
        missing=[schemas.MissingPrice(why=why, provider=p, model=model, unit_label=costs.UNITS.get(unit, unit))
                 for why, p, model, unit in sorted(m.missing)],
        bills=[schemas.BillCheck(provider=r.provider, currency=r.currency, theirs=r.amount, note=r.note,
                                 ours=costs.ours_for_bill(b, m, r.provider, r.currency, name)) for r in bills],
        top_calls=sorted(calls, key=lambda c: -c.rupees)[:TOP_CALLS],
    )


def _months(s, current: str) -> list[str]:
    """Months to pick from: from the first tracked one to now, newest first."""
    now = f"{utc_now():%Y-%m}"
    first = repo.first_usage_at(s)
    start = min(f"{first:%Y-%m}" if first else now, current, now)
    out, y, mo = [], *(int(x) for x in start.split("-"))
    while f"{y:04d}-{mo:02d}" <= max(now, current):
        out.append(f"{y:04d}-{mo:02d}")
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return out[::-1]


# ---------- the price list, rate, allowances, fees, bills ----------

ROWS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "prices": (schemas.PriceIn, schemas.PriceRow),
    "rates": (schemas.RateIn, schemas.RateRow),
    "allowances": (schemas.AllowanceIn, schemas.AllowanceRow),
    "fixed": (schemas.FixedIn, schemas.FixedRow),
    "bills": (schemas.BillIn, schemas.BillRow),
}


def _row(kind: str, row) -> BaseModel:
    out = ROWS[kind][1]
    return out(**{name: getattr(row, name) for name in out.model_fields})


@router.get("/cost-settings", response_model=schemas.CostSettings)
def settings(request: Request):
    with request.app.state.sessions() as s:
        return schemas.CostSettings(
            **{kind: [_row(kind, r) for r in repo.cost_rows(s, kind)] for kind in ROWS},
            units=costs.UNITS,
        )


def _check(kind: str, body: BaseModel) -> dict:
    fields = body.model_dump()
    if kind == "fixed" and fields["valid_to"] is not None and fields["valid_to"] < fields["valid_from"]:
        raise ValueError("The last month can't be before the first.")
    if kind == "prices":
        fields["model"] = fields["model"].strip()
    return fields


def _routes(kind: str, body_type: type[BaseModel], row_type: type[BaseModel]) -> None:
    """Add, change and remove one kind of row; each a typed route, so the
    dashboard's generated types know every field."""

    def add(body: body_type, request: Request):  # type: ignore[valid-type]
        with staff_errors(), request.app.state.sessions() as s:
            return _row(kind, repo.save_cost_row(s, kind, None, _check(kind, body)))

    def change(row_id: int, body: body_type, request: Request):  # type: ignore[valid-type]
        with staff_errors(), request.app.state.sessions() as s:
            return _row(kind, repo.save_cost_row(s, kind, row_id, _check(kind, body)))

    def remove(row_id: int, request: Request) -> dict:
        with staff_errors(), request.app.state.sessions() as s:
            repo.delete_cost_row(s, kind, row_id)
        return {"ok": True}

    path = f"/cost-settings/{kind}"
    router.add_api_route(path, add, methods=["POST"], response_model=row_type, name=f"add_{kind}")
    router.add_api_route(f"{path}/{{row_id}}", change, methods=["PUT"], response_model=row_type, name=f"change_{kind}")
    router.add_api_route(f"{path}/{{row_id}}", remove, methods=["DELETE"], name=f"remove_{kind}")


for _kind, (_body, _out) in ROWS.items():
    _routes(_kind, _body, _out)
