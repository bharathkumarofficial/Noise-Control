# Noise Level Monitor for Library / Study Zones with Alerts

A desktop application (pure software, uses your laptop/PC microphone) that
monitors ambient noise in real time, shows a live graph, classifies the
zone as **QUIET / MODERATE / NOISY**, and raises a visual + audible +
logged **alert** whenever the area gets too loud for a study zone.

---

## 1. Project Overview

**Problem statement:** Libraries and study rooms need to stay quiet, but
there's no automatic way to detect and flag when noise crosses an
acceptable limit. A staff member has to physically notice it.

**Solution:** A software tool that listens through a microphone,
continuously calculates a noise/decibel level, and automatically alerts
when the room becomes too noisy — with a timestamped log for records
(useful for a report/analysis of "noisiest hours", repeat offenders, etc.).

**Objectives**
1. Capture live audio from a microphone.
2. Convert audio signal to a meaningful noise (dB) reading.
3. Display the level live (numeric + graph).
4. Classify noise into zones using configurable thresholds.
5. Trigger an alert (visual flash + beep sound) when the noisy condition
   is sustained.
6. Log every reading/alert event with a timestamp to a CSV file for
   later analysis/reporting.

---

## 2. Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.8+ | Easy audio + GUI support, great for a college project |
| Audio capture | `sounddevice` (built on PortAudio) | Simple, cross-platform mic access |
| Signal processing | `numpy` | RMS / dB math |
| GUI | `tkinter` (built into Python) | No extra install needed |
| Live graph | `matplotlib` embedded in Tkinter | Real-time plotting |
| Data storage | `csv` (built-in) | Lightweight event/alert log |

No paid APIs, no internet connection, and no extra hardware required —
it runs entirely on your laptop's built-in microphone.

---

## 3. How the "Noise Level" is Calculated (the core logic)

A laptop mic isn't a calibrated sound-level meter, so the project uses a
standard, well-accepted approximation technique used in many similar
mini-projects:

1. The mic gives you a stream of audio samples between **-1.0 and 1.0**
   (loudness of the waveform at each instant).
2. We take a small chunk (`BLOCK_SIZE = 1024` samples, about 23 ms) and
   compute its **RMS (Root Mean Square)** — this represents the average
   "energy"/loudness of that chunk:

   ```
   RMS = sqrt(mean(sample^2 for each sample in block))
   ```

3. Convert RMS to **decibels relative to full scale (dBFS)**:

   ```
   dBFS = 20 * log10(RMS)
   ```
   This value is always ≤ 0 (0 = loudest the mic can capture without
   clipping, very negative = near silence).

4. Since dBFS is not intuitive for a report, we shift it with a
   **calibration offset** so it displays like a real-world dB(SPL)
   value (e.g., quiet room ≈ 30–40, normal talking ≈ 55–65, loud
   noise ≈ 70+):

   ```
   Displayed dB = CALIBRATION_OFFSET + dBFS
   ```

This is exactly the same idea used in most Arduino/ESP32 "sound sensor"
projects — the difference is we are extracting it from a laptop mic in
software instead of an analog sensor module.

### Calibration (recommended before your demo/viva)
1. Install any decibel-meter app on your phone (e.g., "Sound Meter").
2. Run the app, note the reading in a quiet room (say phone shows 35 dB).
3. Run `main.py`, note what it shows for the same room.
4. Adjust `CALIBRATION_OFFSET` in `main.py` until your app's number is
   close to the phone's reading. Once set, it stays reasonably
   consistent for demo purposes.

---

## 4. Setup Instructions

### Step 1 — Install Python
Make sure Python 3.8 or newer is installed (`python --version`).

### Step 2 — Get the project files
Place `main.py`, `requirements.txt` in one folder, e.g. `noise_monitor/`.

### Step 3 — (Recommended) Create a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### Step 4 — Install dependencies
```bash
pip install -r requirements.txt
```

> **Linux users:** if `sounddevice` fails to install/import, first run:
> `sudo apt-get install libportaudio2`

### Step 5 — Run the application
```bash
python main.py
```

A window opens. Click **▶ Start Monitoring** and allow microphone
access if your OS prompts for it.

---

## 5. Using the App

| Element | What it does |
|---|---|
| Big number (e.g. `52.3 dB`) | Current live noise level |
| STATUS text | QUIET (green) / MODERATE (yellow) / NOISY (red) |
| Graph | Last ~15 seconds of noise history |
| Quiet max / Moderate max fields | Change thresholds live, no restart needed |
| Start / Stop | Begin or pause microphone capture |
| Reset Alert Count | Zeroes the on-screen alert counter |
| Alerts triggered | Total number of alerts since app opened |

**Alert logic:** if the level stays in the NOISY zone continuously for
**2 seconds**, an alert fires: the window flashes red, a beep tone
plays, the counter increments, and a row is written to `noise_log.csv`.
A 5-second cooldown prevents alert spam from one long noisy period.

---

## 6. The Log File (`noise_log.csv`)

Every start/stop and every alert is recorded:

| timestamp | noise_db | status | event |
|---|---|---|---|
| 2026-09-23 10:15:02 | 0.0 | INFO | Monitoring started |
| 2026-09-23 10:16:40 | 68.4 | NOISY | ALERT |

This file can be opened directly in Excel and is perfect material for
your project report — e.g. a chart of "alerts per hour" or "how many
times the reading room crossed the noise limit today".

---

## 7. Code Walkthrough (for your viva / explanation)

- **`rms_to_db()`** — the core DSP function; converts a raw audio block
  into a displayable dB number (see Section 3).
- **`classify()`** — simple threshold comparison → returns QUIET /
  MODERATE / NOISY.
- **`play_beep()`** — generates a short sine-wave tone in code (no
  external `.wav` file needed) and plays it through the speakers.
- **`NoiseMonitorApp._audio_callback()`** — runs on a background audio
  thread; every time the mic has a new chunk of samples, it's pushed
  into a thread-safe `queue.Queue`.
- **`NoiseMonitorApp._refresh_ui()`** — runs every 100 ms on the main
  GUI thread; pulls the latest audio chunk from the queue, computes dB,
  updates the number/graph/status, and calls `_evaluate()`.
- **`NoiseMonitorApp._evaluate()`** — implements the "sustained noise +
  cooldown" alert rule described above.
- **`log_event()`** — appends a row to the CSV log.

**Why a queue + two threads?** Audio capture must never be blocked
waiting on the GUI (or you get glitches/crashes), and the GUI must
never be blocked waiting on audio. The queue safely hands data from the
audio thread to the GUI thread.

---

## 8. Testing Checklist

1. Start the app in a quiet room → status should show QUIET (green).
2. Talk normally near the mic → should move to MODERATE (yellow).
3. Clap loudly / play loud music for 2+ seconds → should trigger a
   NOISY alert (red flash + beep) and add a row to `noise_log.csv`.
4. Change the threshold fields and confirm classification updates
   immediately.
5. Let it run and confirm the graph keeps scrolling with new data.
6. Stop and re-Start monitoring — confirm it resumes cleanly.

---

## 9. Possible Project Extensions (for bonus marks)

- **Hardware version:** replace the laptop mic with an ESP32/Arduino +
  sound sensor module (e.g., KY-038) that sends readings over Wi-Fi/
  Serial to this same Python app — turns it into an IoT project.
- **Email/SMS/Telegram alert:** call an API (e.g., `smtplib` for email,
  or a Telegram bot) inside `_trigger_alert()` to notify a librarian
  remotely.
- **Web dashboard:** expose live readings over a small Flask server so
  multiple study rooms can be monitored from one browser page.
- **Data analytics:** use `pandas` + `matplotlib` on `noise_log.csv` to
  generate a "noise heatmap by hour of day" for your report.
- **Multiple zones:** run one instance per room, each writing to its
  own log file, and combine results in a dashboard.

---

## 10. Likely Viva / Exam Questions

**Q: How do you calculate noise level from audio without a special sensor?**
A: By computing the RMS (root-mean-square) energy of the audio
waveform and converting it to decibels using `20*log10(RMS)` — the
same math used inside any real sound level meter.

**Q: Why is a calibration offset needed?**
A: A laptop mic outputs dBFS (relative to its own maximum), not real
sound-pressure-level dB. The offset maps it to a realistic-looking dB
scale for the room, matched roughly against a reference meter.

**Q: Why use threading/a queue instead of processing audio directly in the GUI loop?**
A: Audio callbacks must run in real time with minimal delay; if they
were coupled directly to a (possibly slow) GUI redraw, you'd get audio
dropouts. The queue decouples the two so each runs smoothly on its own
schedule.

**Q: How would you turn this into an IoT project?**
A: Replace the `sounddevice` mic capture with data received from a
physical sound sensor + microcontroller (ESP32) sent over Wi-Fi/MQTT/
Serial, keeping the rest of the logic (dB conversion, thresholds,
alerts, logging) unchanged.

---

## 11. Folder Structure

```
noise_monitor/
├── main.py            # full application (GUI + audio + logic)
├── requirements.txt   # pip dependencies
├── noise_log.csv      # auto-created on first run (event log)
└── README.md          # this guide
```

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `PortAudioError` / mic not found | Check OS microphone permissions; try a different `device` index with `sd.query_devices()` |
| App shows dB near 0 or constant | Mic might be muted at the OS level, or `CALIBRATION_OFFSET` too low |
| No sound on alert | Check system output volume / default playback device |
| Graph window blank | Make sure `matplotlib` installed correctly (`pip show matplotlib`) |
| `ModuleNotFoundError` | Re-run `pip install -r requirements.txt` inside the correct virtual environment |

---

You now have a complete, working, explainable software project — ready
to demo, submit, and defend in a viva.
