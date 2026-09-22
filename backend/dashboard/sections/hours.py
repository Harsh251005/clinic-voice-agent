"""Weekly hours per doctor: one row per day, up to two sittings (a morning and
an evening, say). Quick actions fill the week; nothing is saved until Save."""

from __future__ import annotations

from datetime import time, timedelta
from types import SimpleNamespace

import streamlit as st

from clinic_agent.prompts import weekly_hours
from clinic_agent.store import repo
from dashboard import data, schedules, theme

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STEP = timedelta(minutes=15)
FIELDS = ("open", "s1", "e1", "two", "s2", "e2")


def render(clinic) -> None:
    if not clinic.doctors:
        st.markdown('<p class="muted">Add a doctor first.</p>', unsafe_allow_html=True)
        return

    names = {d.id: d.name for d in clinic.doctors}
    doctor_id = st.selectbox("Doctor", list(names), format_func=names.get, key="hours_doctor")
    doctor = next(d for d in clinic.doctors if d.id == doctor_id)
    others = [d for d in clinic.doctors if d.id != doctor_id and d.hours]
    saved = schedules.same_as(doctor)
    _load(doctor_id, saved)

    with theme.card("hours_quick"):
        st.markdown('<p class="card-title">Fill the week</p>', unsafe_allow_html=True)
        patterns = {name: sittings for name, sittings in schedules.PRESETS.items()}
        patterns.update({f"Same as {d.name}": schedules.same_as(d) for d in others})
        pick, apply, copy = st.columns([3, 1, 2], vertical_alignment="bottom")
        choice = pick.selectbox(
            "Start from a pattern", list(patterns), index=None,
            placeholder="Choose a common pattern…", key=f"pattern_{doctor_id}",
        )
        apply.button(
            "Apply", key=f"apply_{doctor_id}", disabled=choice is None, width="stretch",
            on_click=_fill, args=(doctor_id, patterns.get(choice, [])),
        )
        copy.button(
            "Copy Monday to all open days", key=f"copy_{doctor_id}", width="stretch",
            on_click=_copy_monday, args=(doctor_id,),
        )

    with theme.card("hours"):
        title, badge = st.columns([3, 1])
        title.markdown(f'<p class="card-title">{doctor.name}\'s week</p>', unsafe_allow_html=True)
        current = _sittings(doctor_id)
        if current is not None and sorted(current) != sorted(saved):
            badge.markdown(theme.pill("Unsaved changes", "warn"), unsafe_allow_html=True)
        if any(sum(1 for w, *_ in saved if w == day) > 2 for day in range(7)):
            st.warning("Some days have more than two sittings. This table shows and saves the first two.")

        head = st.columns([1.3, 0.8, 1.1, 1.1, 1.2, 1.1, 1.1])
        for col, label in zip(head, ["Day", "Open", "From", "To", "Second sitting", "From", "To"]):
            col.markdown(f'<p class="muted">{label}</p>', unsafe_allow_html=True)
        for day, name in enumerate(DAYS):
            _day_row(doctor_id, day, name)

        errors = _problems(doctor_id)
        preview = weekly_hours(SimpleNamespace(hours=[
            SimpleNamespace(weekday=w, start=a, end=b) for w, a, b in sorted(current or [])
        ]))
        st.markdown(f'<p class="muted">The receptionist will say: <b>{preview}</b></p>', unsafe_allow_html=True)

        save, discard = st.columns([1, 1])
        if save.button("Save hours", type="primary", key=f"save_hours_{doctor_id}", width="stretch"):
            if errors:
                st.error(" ".join(errors))
                return
            try:
                with data.session() as s:
                    repo.set_doctor_hours(s, doctor_id, current)
            except ValueError as err:
                st.error(str(err))
                return
            theme.flash(f"Hours saved for {doctor.name}")
            st.rerun()
        discard.button("Discard changes", key=f"discard_{doctor_id}", width="stretch",
                       on_click=_forget, args=(doctor_id,))


def _key(doctor_id: int, day: int, field: str) -> str:
    return f"hr{doctor_id}_{day}_{field}"


def _load(doctor_id: int, sittings) -> None:
    """Put the saved week into widget state, once; edits then live there."""
    if _key(doctor_id, 0, "open") in st.session_state:
        return
    _fill(doctor_id, sittings)


def _fill(doctor_id: int, sittings) -> None:
    for day in range(7):
        spans = sorted((a, b) for w, a, b in sittings if w == day)
        first = spans[0] if spans else schedules.MORNING
        second = spans[1] if len(spans) > 1 else schedules.EVENING
        values = {
            "open": bool(spans), "s1": first[0], "e1": first[1],
            "two": len(spans) > 1, "s2": second[0], "e2": second[1],
        }
        for field, value in values.items():
            st.session_state[_key(doctor_id, day, field)] = value


def _copy_monday(doctor_id: int) -> None:
    for day in range(1, 7):
        if st.session_state[_key(doctor_id, day, "open")]:
            for field in ("s1", "e1", "two", "s2", "e2"):
                st.session_state[_key(doctor_id, day, field)] = st.session_state[_key(doctor_id, 0, field)]


def _forget(doctor_id: int) -> None:
    for day in range(7):
        for field in FIELDS:
            st.session_state.pop(_key(doctor_id, day, field), None)


def _day_row(doctor_id: int, day: int, name: str) -> None:
    k = lambda field: _key(doctor_id, day, field)  # noqa: E731
    cols = st.columns([1.3, 0.8, 1.1, 1.1, 1.2, 1.1, 1.1], vertical_alignment="center")
    is_open = st.session_state[k("open")]
    two = st.session_state[k("two")]
    cols[0].markdown(f"**{name}**" if is_open else f'<span class="muted">{name}</span>', unsafe_allow_html=True)
    cols[1].toggle(f"{name} open", key=k("open"), label_visibility="collapsed")
    cols[2].time_input(f"{name} from", key=k("s1"), step=STEP, disabled=not is_open, label_visibility="collapsed")
    cols[3].time_input(f"{name} to", key=k("e1"), step=STEP, disabled=not is_open, label_visibility="collapsed")
    cols[4].toggle(f"{name} second sitting", key=k("two"), disabled=not is_open, label_visibility="collapsed")
    cols[5].time_input(f"{name} second from", key=k("s2"), step=STEP, disabled=not (is_open and two), label_visibility="collapsed")
    cols[6].time_input(f"{name} second to", key=k("e2"), step=STEP, disabled=not (is_open and two), label_visibility="collapsed")


def _sittings(doctor_id: int) -> list[tuple[int, time, time]] | None:
    """The week as (weekday, start, end) rows, from the table's current state."""
    state = st.session_state
    if _key(doctor_id, 0, "open") not in state:
        return None
    rows = []
    for day in range(7):
        k = lambda field: state[_key(doctor_id, day, field)]  # noqa: E731
        if k("open"):
            rows.append((day, k("s1"), k("e1")))
            if k("two"):
                rows.append((day, k("s2"), k("e2")))
    return rows


def _problems(doctor_id: int) -> list[str]:
    state, problems = st.session_state, []
    for day, name in enumerate(DAYS):
        k = lambda field: state[_key(doctor_id, day, field)]  # noqa: E731
        if not k("open"):
            continue
        if k("e1") <= k("s1"):
            problems.append(f"{name}: the sitting must end after it starts.")
        if k("two"):
            if k("e2") <= k("s2"):
                problems.append(f"{name}: the second sitting must end after it starts.")
            elif k("s2") < k("e1"):
                problems.append(f"{name}: the second sitting starts before the first one ends.")
    return problems
