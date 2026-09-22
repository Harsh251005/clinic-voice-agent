"""The call-link server: patients open /call/<slug> and talk in the browser.

It looks the clinic up by its link name and hands the browser a signed,
short-lived LiveKit join pass that dispatches the receptionist with the
clinic's id (clinic_agent/dispatch.py). It never talks to the patient itself.

    uv run python -m api
"""
