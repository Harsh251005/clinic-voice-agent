"""What things cost, in rupees: exact usage × the price valid on the day.

No vendor returns the price of a call (checked 2026-10-13); every one
reports exact usage, and their price lists are public. So a call's usage is
stored (models.Usage) and priced here when shown, from the price list the
operator keeps in the admin panel (models.Price, ExchangeRate, Allowance,
FixedCost). A corrected price corrects every call it covers.

Plain functions over rows, like booking.py: nothing here touches the
database.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

UNITS = {  # unit -> how the admin panel says it
    "tokens_in": "words read (tokens)",
    "tokens_cached": "words read again, cached (tokens)",
    "tokens_out": "words written (tokens)",
    "seconds_heard": "seconds heard",
    "characters": "characters spoken",
    "minutes": "call minutes",
}
SINGULAR = {"seconds_heard": "second heard", "characters": "character spoken", "minutes": "call minute"}


def per_text(per: float, unit: str) -> str:
    """How a price's quantity reads: "million words read (tokens)", "hour
    heard", "1,000 characters spoken", "call minute"."""
    words = UNITS.get(unit, unit)
    if unit == "seconds_heard" and per == 3600:
        return "hour heard"
    if per == 1:
        return SINGULAR.get(unit, words)
    if per == 1_000_000:
        return f"million {words}"
    return f"{per:,.0f} {words}"


PARTS = ("listening", "thinking", "speaking", "call_line", "other")
PROVIDERS = ("sarvam", "elevenlabs", "openai", "livekit")
CURRENCIES = ("INR", "USD")


@dataclass(frozen=True)
class Priced:
    """One usage row with its price. `rupees` is None when it can't be
    priced: `missing` says why."""

    usage: object  # models.Usage
    rupees: float | None
    native: float | None  # in the price's own currency
    currency: str
    missing: str = ""  # "price" | "rate"


class PriceBook:
    """The price list as it stood on any day."""

    def __init__(self, prices, rates) -> None:
        self._prices: dict[tuple[str, str, str], list] = defaultdict(list)
        for p in sorted(prices, key=lambda p: p.valid_from):
            self._prices[(p.provider, p.model, p.unit)].append(p)
        self._rates = sorted(rates, key=lambda r: r.valid_from)

    def price(self, provider: str, model: str, unit: str, day: date):
        """The model's own price on that day, else the vendor's any-model one."""
        for key in ((provider, model, unit), (provider, "", unit)):
            found = _latest(self._prices.get(key, []), day)
            if found is not None:
                return found
        return None

    def rate(self, day: date) -> float | None:
        found = _latest(self._rates, day)
        return found.inr_per_usd if found else None

    def to_rupees(self, amount: float, currency: str, day: date) -> float | None:
        if currency == "INR":
            return amount
        rate = self.rate(day)
        return None if rate is None else amount * rate

    def priced(self, u) -> Priced:
        day = u.at.date()
        p = self.price(u.provider, u.model, u.unit, day)
        if p is None:
            return Priced(u, None, None, "", missing="price")
        native = u.quantity / p.per * p.amount
        rupees = self.to_rupees(native, p.currency, day)
        return Priced(u, rupees, native, p.currency, missing="" if rupees is not None else "rate")


def _latest(rows, day: date):
    """The row in force on `day`: the last one starting on or before it."""
    found = None
    for r in rows:  # sorted by valid_from
        if r.valid_from <= day:
            found = r
    return found


# ---------- a month ----------


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """"2026-10" -> its first moment and the next month's (naive UTC)."""
    year, mon = (int(x) for x in month.split("-"))
    start = datetime(year, mon, 1)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1)
    return start, end


@dataclass
class FreeShare:
    provider: str
    unit: str
    allowance: float
    used: float
    free: float  # min(used, allowance)
    rupees: float  # what the free part would have cost


@dataclass
class Month:
    priced: list[Priced]
    free: list[FreeShare] = field(default_factory=list)
    fixed: list[tuple[object, float | None]] = field(default_factory=list)  # (FixedCost, rupees)

    @property
    def usage_rupees(self) -> float:
        return sum(p.rupees or 0 for p in self.priced)

    @property
    def free_rupees(self) -> float:
        return sum(f.rupees for f in self.free)

    @property
    def fixed_rupees(self) -> float:
        return sum(r or 0 for _, r in self.fixed)

    @property
    def to_pay(self) -> float:
        return self.usage_rupees - self.free_rupees + self.fixed_rupees

    @property
    def missing(self) -> set[tuple[str, str, str, str]]:
        """(why, provider, model, unit) of everything that couldn't be priced."""
        return {(p.missing, p.usage.provider, p.usage.model, p.usage.unit) for p in self.priced if p.missing}


def month(book: PriceBook, month_name: str, usage, allowances, fixed_costs) -> Month:
    """A month's usage priced, its free allowances taken off at the average
    price paid for that usage, and its fixed fees added."""
    start, end = month_bounds(month_name)
    first, last = start.date(), (end - timedelta(days=1)).date()
    out = Month([book.priced(u) for u in usage if start <= u.at < end])

    latest: dict[tuple[str, str], object] = {}
    for a in sorted(allowances, key=lambda a: a.valid_from):
        if a.valid_from <= last:
            latest[(a.provider, a.unit)] = a
    for (provider, unit), a in latest.items():
        rows = [p for p in out.priced if p.usage.provider == provider and p.usage.unit == unit and p.rupees is not None]
        used = sum(p.usage.quantity for p in rows)
        free = min(used, a.quantity)
        rupees = sum(p.rupees for p in rows) * (free / used) if used else 0.0
        out.free.append(FreeShare(provider, unit, a.quantity, used, free, rupees))

    for f in fixed_costs:
        if f.valid_from <= last and (f.valid_to is None or f.valid_to >= first):
            out.fixed.append((f, book.to_rupees(f.amount, f.currency, first)))
    return out


def ours_for_bill(book: PriceBook, m: Month, provider: str, currency: str, month_name: str) -> float | None:
    """What our numbers say the vendor should bill for the month, in the
    bill's currency: usage less its free allowance, plus its fixed fees.
    None if part of it couldn't be priced or converted."""
    day = month_bounds(month_name)[0].date()
    rate = book.rate(day)

    def convert(amount: float, frm: str) -> float | None:
        if frm == currency:
            return amount
        if rate is None:
            return None
        return amount * rate if currency == "INR" else amount / rate

    total = 0.0
    for p in m.priced:
        if p.usage.provider != provider:
            continue
        if p.native is None:
            return None
        part = convert(p.native, p.currency)
        if part is None:
            return None
        total += part
    for share in m.free:
        if share.provider == provider and share.rupees:
            part = convert(share.rupees, "INR")
            if part is None:
                return None
            total -= part
    for f, _ in m.fixed:
        if f.provider == provider:
            part = convert(f.amount, f.currency)
            if part is None:
                return None
            total += part
    return total
