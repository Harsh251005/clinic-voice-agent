// The call page: ask our server for a join pass, join the LiveKit room, send
// the microphone and play the receptionist. The pass already tells LiveKit
// which clinic's receptionist to send in; this page never decides that.
(() => {
  "use strict";
  const LK = window.LivekitClient;
  const slug = document.querySelector("main").dataset.slug;
  const button = document.getElementById("call");
  const statusEl = document.getElementById("status");
  const timerEl = document.getElementById("timer");
  const ring = document.querySelector(".ring");

  const NO_ANSWER_MS = 20000; // the receptionist normally joins within a few seconds
  let room = null;
  let noAnswer = null;
  let clock = null;
  let ending = false;

  function show(state, text) {
    document.body.className = state;
    statusEl.textContent = text;
    button.disabled = state === "connecting";
    button.setAttribute("aria-label", state === "live" || state === "waiting" ? "End the call" : "Start the call");
  }

  function startClock() {
    const started = Date.now();
    timerEl.hidden = false;
    clock = setInterval(() => {
      const s = Math.floor((Date.now() - started) / 1000);
      timerEl.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }, 500);
  }

  function cleanup() {
    clearTimeout(noAnswer);
    clearInterval(clock);
    timerEl.hidden = true;
    timerEl.textContent = "00:00";
    ring.style.transform = "";
    document.querySelectorAll("audio[data-lk]").forEach((el) => el.remove());
  }

  function receptionistJoined() {
    clearTimeout(noAnswer);
    show("live", "Connected. Speak any time.");
    startClock();
  }

  async function start() {
    ending = false;
    show("connecting", "Connecting…");
    let pass;
    try {
      const res = await fetch(`/call/${encodeURIComponent(slug)}/pass`, { method: "POST" });
      pass = await res.json();
      if (!res.ok) throw new Error(pass.error || "The call could not start.");
    } catch (err) {
      return show("error", err.message || "No connection. Check your internet and try again.");
    }

    room = new LK.Room();
    room
      .on(LK.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === "audio") {
          const el = track.attach();
          el.dataset.lk = "1";
          document.body.appendChild(el);
        }
      })
      .on(LK.RoomEvent.ParticipantConnected, (p) => { if (p.isAgent) receptionistJoined(); })
      .on(LK.RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agent = speakers.find((p) => p.isAgent);
        ring.style.transform = agent ? `scale(${1 + Math.min(agent.audioLevel * 0.8, 0.22)})` : "";
      })
      .on(LK.RoomEvent.Disconnected, () => {
        cleanup();
        room = null;
        // The receptionist ends calls by closing the room; either way the call is over.
        if (!ending && document.body.className !== "error") show("ended", "Call ended. Thank you!");
      });

    try {
      await room.connect(pass.url, pass.token);
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      ending = true;
      if (room) await room.disconnect();
      const denied = err && (err.name === "NotAllowedError" || /permission/i.test(err.message || ""));
      return show("error", denied
        ? "Allow microphone access to talk, then tap again."
        : "The call could not connect. Please try again.");
    }

    if ([...room.remoteParticipants.values()].some((p) => p.isAgent)) return receptionistJoined();
    show("waiting", "Connecting you to the receptionist…");
    noAnswer = setTimeout(async () => {
      ending = true;
      if (room) await room.disconnect();
      show("error", "The receptionist couldn't answer just now. Please try again in a minute.");
    }, NO_ANSWER_MS);
  }

  async function hangUp() {
    ending = true;
    if (room) await room.disconnect();
    show("ended", "Call ended. Thank you!");
  }

  button.addEventListener("click", () => {
    const state = document.body.className;
    if (state === "live" || state === "waiting") hangUp();
    else if (state !== "connecting") start();
  });

  if (!LK) show("error", "This page could not load. Refresh and try again.");
})();
