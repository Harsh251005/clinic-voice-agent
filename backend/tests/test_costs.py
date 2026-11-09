"""What calls cost (Harsh, 2026-10-13): each call's exact usage is kept,
priced in rupees with the price list the admin edits, and checked against
the vendors' bills. Nothing about it needs a code change."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from livekit.agents.metrics import LLMModelUsage, STTModelUsage, TTSModelUsage

from clinic_agent import costs, incidents
from clinic_agent.call_record import CallRecorder
from clinic_agent.config import load_settings
from clinic_agent.lines import Line
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import Usage, utc_now
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture

HINDI = Line("hi", stt="sarvam", llm="sarvam", tts="sarvam")

ADMIN = "harsh@example.com"
DAY = datetime(2026, 10, 12, 9)


def _row(**kw):
    return SimpleNamespace(**{"model": "", "valid_from": date(2026, 10, 1), **kw})


def _use(provider, model, unit, quantity, at=DAY, **kw):
    return SimpleNamespace(provider=provider, model=model, unit=unit, quantity=quantity, at=at,
                           source="call", part="thinking", call_id=1, clinic_id=1, language="hi", **kw)


BOOK = costs.PriceBook(
    prices=[
        _row(provider="sarvam", unit="seconds_heard", amount=30, per=3600, currency="INR"),
        _row(provider="openai", model="gpt-4.1-mini", unit="tokens_out", amount=1.60, per=1e6, currency="USD"),
        _row(provider="openai", model="gpt-4.1-mini", unit="tokens_out", amount=2.00, per=1e6, currency="USD",
             valid_from=date(2026, 11, 1)),
        _row(provider="livekit", model="agent_session", unit="minutes", amount=0.01, per=1, currency="USD"),
    ],
    rates=[_row(inr_per_usd=90.0), _row(inr_per_usd=100.0, valid_from=date(2026, 11, 1))],
)


# ---------- pricing ----------

def test_usage_is_priced_at_the_price_and_rate_of_its_own_day():
    assert BOOK.priced(_use("sarvam", "saaras:v3", "seconds_heard", 120)).rupees == pytest.approx(1.0)  # any-model price
    october = BOOK.priced(_use("openai", "gpt-4.1-mini", "tokens_out", 1e6))
    november = BOOK.priced(_use("openai", "gpt-4.1-mini", "tokens_out", 1e6, at=datetime(2026, 11, 2)))
    assert (october.rupees, october.native, october.currency) == (pytest.approx(144.0), pytest.approx(1.60), "USD")
    assert november.rupees == pytest.approx(200.0)  # the new price and the new rate, the past untouched


def test_what_cant_be_priced_says_why():
    assert BOOK.priced(_use("sarvam", "bulbul:v3", "characters", 60)).missing == "price"
    no_rate = costs.PriceBook(BOOK._prices["openai", "gpt-4.1-mini", "tokens_out"], [])
    assert no_rate.priced(_use("openai", "gpt-4.1-mini", "tokens_out", 10)).missing == "rate"
    before = BOOK.priced(_use("sarvam", "", "seconds_heard", 60, at=datetime(2026, 9, 30)))
    assert (before.rupees, before.missing) == (None, "price")  # no price yet on that day


def test_a_month_takes_off_the_free_allowance_and_adds_fixed_fees():
    usage = [_use("livekit", "agent_session", "minutes", 1_500)]  # $15 = ₹1,350
    m = costs.month(
        BOOK, "2026-10", usage,
        allowances=[_row(provider="livekit", unit="minutes", quantity=1_000)],
        fixed_costs=[_row(name="Ship", provider="livekit", amount=5, currency="USD", valid_to=None)],
    )
    assert m.usage_rupees == pytest.approx(1350.0)
    assert m.free_rupees == pytest.approx(900.0)  # 1,000 of the 1,500 minutes
    assert m.to_pay == pytest.approx(1350 - 900 + 450)
    # The vendor's bill is compared in its own currency: $5 of minutes + $5 plan.
    assert costs.ours_for_bill(BOOK, m, "livekit", "USD", "2026-10") == pytest.approx(10.0)


def test_months_have_bounds():
    assert costs.month_bounds("2026-12") == (datetime(2026, 12, 1), datetime(2027, 1, 1))


# ---------- recording what a call used ----------

def _session(model_usage):
    return SimpleNamespace(
        usage=SimpleNamespace(model_usage=model_usage),
        llm=SimpleNamespace(model="sarvam-105b-conversations"),
        stt=SimpleNamespace(model="saaras:v3"), tts=SimpleNamespace(model="bulbul:v3"),
    )


def test_a_call_records_each_vendors_exact_usage_and_its_minutes():
    record = CallRecorder(None, 1, "room-1", "stack", "hi", line=HINDI)
    record.session = _session([
        LLMModelUsage(provider="Sarvam", model="", input_tokens=5000, input_cached_tokens=3000, output_tokens=400),
        STTModelUsage(provider="Sarvam", model="saaras:v3", audio_duration=42.5),
        TTSModelUsage(provider="Sarvam", model="bulbul:v3", characters_count=880),
    ])
    used = {(u["part"], u["provider"], u["model"], u["unit"]): u["quantity"]
            for u in record.usage(record.started_at + timedelta(minutes=3))}
    assert used == {
        ("call_line", "livekit", "agent_session", "minutes"): pytest.approx(3.0),
        ("thinking", "sarvam", "sarvam-105b-conversations", "tokens_in"): 2000,  # cached ones are priced apart
        ("thinking", "sarvam", "sarvam-105b-conversations", "tokens_cached"): 3000,
        ("thinking", "sarvam", "sarvam-105b-conversations", "tokens_out"): 400,
        ("listening", "sarvam", "saaras:v3", "seconds_heard"): 42.5,
        ("speaking", "sarvam", "bulbul:v3", "characters"): 880,
    }


def test_the_console_spends_no_livekit_minutes_and_a_broken_count_loses_only_itself():
    record = CallRecorder(None, 1, repo.CONSOLE_ROOM, "stack", "hi", line=Line("hi", stt="sarvam", llm="openai", tts="sarvam"))
    record.session = SimpleNamespace(usage=None)  # reading it fails
    assert record.usage(record.started_at + timedelta(minutes=2)) == []


def _sessions():
    return sessions_for(load_settings().database_url)


def _priced_call(clinic_id, *, test=False, ago=timedelta(minutes=5)):
    started = utc_now() - ago
    with _sessions()() as s:
        call = repo.start_call(s, clinic_id, "room", "stack", "hi", started, test)
        repo.finish_call(
            s, call.id, ended_at=started + timedelta(minutes=2), end_reason="agent_ended", outcome="info_only",
            turn_count=2, error_count=0, appointments=[], events=[], transcript=[], purge_after=started + timedelta(days=30),
            usage=[
                {"part": "listening", "provider": "sarvam", "model": "saaras:v3", "unit": "seconds_heard", "quantity": 120.0},
                {"part": "speaking", "provider": "sarvam", "model": "bulbul:v3", "unit": "characters", "quantity": 1000.0},
                {"part": "call_line", "provider": "livekit", "model": "agent_session", "unit": "minutes", "quantity": 2.0},
            ],
        )
        return call.id


def test_an_erased_test_call_still_cost_what_it_cost(world):  # noqa: F811
    call_id = _priced_call(world["cure"], test=True)
    with _sessions()() as s:
        repo.erase_test_calls(s, [call_id])
        rows = repo.usage_between(s, utc_now() - timedelta(days=1), utc_now())
    assert {(u.call_id, u.test, u.clinic_name) for u in rows} == {(None, True, "Cure Dental Clinic")}


# ---------- the admin panel ----------

ROUTES = [
    ("GET", "/api/admin/costs"), ("GET", "/api/admin/cost-settings"),
    *((m, f"/api/admin/cost-settings/{kind}{tail}") for kind in ("prices", "rates", "allowances", "fixed", "bills")
      for m, tail in (("POST", ""), ("PUT", "/1"), ("DELETE", "/1"))),
    ("POST", "/api/admin/cost-settings/model-prices"), ("DELETE", "/api/admin/cost-settings/model-prices?ids=1"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_only_admins(world, method, path):  # noqa: F811
    assert client_as("reception@cure.in").request(method, path, json={}).status_code == 403


def test_the_month_and_each_call_in_rupees(world):  # noqa: F811
    patient = _priced_call(world["cure"])
    _priced_call(world["demo"], test=True)
    c = client_as(ADMIN, admin=True)
    m = c.get("/api/admin/costs").json()
    # Seeded official prices: ₹30/hour heard, ₹30 per 10,000 characters, LiveKit free plan.
    per_call = 30 * 120 / 3600 + 30 * 1000 / 10_000  # ₹1 + ₹3
    assert (m["calls"], m["test_calls"]) == (1, 1)
    assert m["usage_rupees"] == pytest.approx(2 * per_call)
    assert m["per_call_rupees"] == pytest.approx(per_call)
    assert {s["key"]: s["rupees"] for s in m["by_part"]} == pytest.approx({"listening": 2.0, "speaking": 6.0, "call_line": 0.0})
    assert m["missing"] == []
    trace = c.get(f"/api/admin/calls/{patient}").json()["cost"]
    assert (trace["rupees"], trace["complete"]) == (pytest.approx(per_call), True)
    assert {(line["unit_label"], line["price"]) for line in trace["lines"]} >= {("seconds heard", "₹30 per hour heard")}


def test_a_model_without_a_price_is_flagged_until_its_price_is_added(world):  # noqa: F811
    with _sessions()() as s:
        repo.add_usage(s, world["cure"], utc_now(), "call", "thinking",
                       [{"provider": "openai", "model": "gpt-4.1", "unit": "tokens_in", "quantity": 600.0}])
        incidents.sync(s, utc_now(), max_call_minutes=5)
        assert [(i.kind, i.subject) for i in repo.open_incidents(s) if i.kind == "price_missing"] == [
            ("price_missing", "openai/gpt-4.1/tokens_in")]
    c = client_as(ADMIN, admin=True)
    (missing,) = c.get("/api/admin/costs").json()["missing"]
    assert missing == {"why": "price", "provider": "openai", "model": "gpt-4.1", "unit_label": "words read (tokens)"}
    problem = next(p for p in c.get("/api/admin/problems").json()["open"] if p["kind"] == "price_missing")
    assert "OpenAI gpt-4.1 has no price" in problem["title"]
    # Open goes straight to the missing price, filled in: vendor, model, unit and the day it was first used
    assert problem["link"] == f"/admin/costs/prices?add=openai%2Fgpt-4.1%2Ftokens_in&from={utc_now():%Y-%m-%d}"
    used = c.get("/api/admin/cost-settings").json()["used"]
    assert {"provider": "openai", "model": "gpt-4.1", "unit": "tokens_in"}.items() <= next(
        u for u in used if u["model"] == "gpt-4.1").items()  # the page can tell which prices match no calls
    c.post("/api/admin/cost-settings/prices", json={
        "provider": "openai", "model": "gpt-4.1", "unit": "tokens_in",
        "amount": 2.00, "per": 1_000_000, "currency": "USD", "valid_from": "2026-10-01"})
    with _sessions()() as s:
        assert not [i for i in repo.open_incidents(s) if i.kind == "price_missing"]  # the save itself re-checked


def test_everything_is_edited_in_the_panel(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    settings = c.get("/api/admin/cost-settings").json()
    assert settings["rates"][0]["inr_per_usd"] == 95.0 and len(settings["prices"]) == 18  # the seeded list, ElevenLabs gone
    rate = settings["rates"][0]
    assert c.put(f"/api/admin/cost-settings/rates/{rate['id']}", json=rate | {"inr_per_usd": 88.5}).json()["inr_per_usd"] == 88.5
    clash = c.post("/api/admin/cost-settings/rates", json={"valid_from": rate["valid_from"], "inr_per_usd": 90})
    assert (clash.status_code, clash.json()["detail"]) == (422, "There is already a rate from that date: change that one.")
    bad = c.post("/api/admin/cost-settings/fixed", json={"name": "Plan", "provider": "livekit", "amount": 5,
                                                         "currency": "USD", "valid_from": "2026-11-01", "valid_to": "2026-10-01"})
    assert bad.status_code == 422
    assert c.post("/api/admin/cost-settings/prices", json={"provider": "acme", "unit": "minutes", "amount": 1, "per": 1,
                                                          "currency": "USD", "valid_from": "2026-10-01"}).status_code == 422
    bill = c.post("/api/admin/cost-settings/bills", json={"month": f"{utc_now():%Y-%m}", "provider": "sarvam",
                                                         "amount": 10, "currency": "INR"}).json()
    _priced_call(world["cure"])
    (check,) = c.get("/api/admin/costs").json()["bills"]
    assert (check["theirs"], check["ours"]) == (10, pytest.approx(4.0))
    assert c.delete(f"/api/admin/cost-settings/bills/{bill['id']}").json() == {"ok": True}
    assert c.delete(f"/api/admin/cost-settings/bills/{bill['id']}").status_code == 404


def test_a_language_models_token_prices_are_saved_and_corrected_as_one(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)

    def model_rows(model):
        return {r["unit"]: r for r in c.get("/api/admin/cost-settings").json()["prices"] if r["model"] == model}

    body = {"provider": "openai", "model": " gpt-test ", "currency": "USD", "valid_from": "2026-11-01",
            "tokens_in": 0.4, "tokens_cached": 0.1, "tokens_out": 1.6}
    saved = c.post("/api/admin/cost-settings/model-prices", json=body).json()
    assert {(r["unit"], r["amount"], r["per"], r["model"]) for r in saved} == {
        ("tokens_in", 0.4, 1e6, "gpt-test"), ("tokens_cached", 0.1, 1e6, "gpt-test"), ("tokens_out", 1.6, 1e6, "gpt-test")}

    # A correction replaces all three at once.
    ids = [r["id"] for r in model_rows("gpt-test").values()]
    c.post("/api/admin/cost-settings/model-prices", json=body | {"tokens_out": 2.0, "replace": ids})
    assert {u: r["amount"] for u, r in model_rows("gpt-test").items()} == {"tokens_in": 0.4, "tokens_cached": 0.1, "tokens_out": 2.0}

    # Never a speech price through here, and a refusal changes nothing.
    speech = next(r for r in c.get("/api/admin/cost-settings").json()["prices"] if r["unit"] == "seconds_heard")
    ids = [r["id"] for r in model_rows("gpt-test").values()]
    refused = c.post("/api/admin/cost-settings/model-prices", json=body | {"replace": [*ids, speech["id"]]})
    assert (refused.status_code, refused.json()["detail"]) == (422, "Only a language model's token prices can be changed together.")
    assert len(model_rows("gpt-test")) == 3
    assert c.post("/api/admin/cost-settings/model-prices", json=body | {"replace": [999_999]}).status_code == 404
    assert len(model_rows("gpt-test")) == 3

    query = "&".join(f"ids={i}" for i in ids)
    assert c.delete(f"/api/admin/cost-settings/model-prices?{query}").json() == {"ok": True}
    assert model_rows("gpt-test") == {}


def test_the_livekit_warning_follows_the_allowance_set_in_the_panel(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    (row,) = [a for a in c.get("/api/admin/cost-settings").json()["allowances"] if a["provider"] == "livekit"]
    c.put(f"/api/admin/cost-settings/allowances/{row['id']}", json=row | {"quantity": 2})
    _priced_call(world["cure"], ago=timedelta(minutes=5))  # 2 minutes of the 2 allowed
    with _sessions()() as s:
        incidents.sync(s, utc_now(), max_call_minutes=5)
        (inc,) = [i for i in repo.open_incidents(s) if i.kind == "livekit_minutes"]
    assert inc.severity == "critical"


def test_usage_rows_hold_counts_never_words():
    assert {c.name for c in Usage.__table__.columns} == {
        "id", "at", "clinic_id", "clinic_name", "call_id", "language", "test", "source", "part",
        "provider", "model", "unit", "quantity"}


def test_every_vendor_a_call_can_use_is_counted_in_the_right_units():
    # COUNTED_IN is what a price may name; it must follow the vendors calls can actually use.
    from clinic_agent import costs
    from clinic_agent.providers import llm, stt, tts

    for vendor in stt.BUILDERS:
        assert "seconds_heard" in costs.COUNTED_IN[vendor]
    for vendor in tts.BUILDERS:
        assert "characters" in costs.COUNTED_IN[vendor]
    for vendor in llm.BUILDERS:
        assert set(costs.TOKENS) <= set(costs.COUNTED_IN[vendor])


def test_a_price_in_a_unit_its_vendor_is_never_counted_in_is_refused(world):  # noqa: F811
    # Seen on the real data (2026-11-09): "speech-to-text" per minute for Sarvam, which counts listening in seconds.
    c = client_as(ADMIN, admin=True)
    r = c.post("/api/admin/cost-settings/prices", json={
        "provider": "sarvam", "model": "speech-to-text", "unit": "minutes",
        "amount": 0.49, "per": 1, "currency": "INR", "valid_from": "2026-11-09"})
    assert r.status_code == 422 and "Calls never count Sarvam in call minutes" in r.json()["detail"]
    assert "seconds heard" in r.json()["detail"]
