"""
Noise Level Monitor for Library / Study Zones with Alerts
"""

import csv, os, time, queue, threading
import smtplib
from email.message import EmailMessage
from collections import deque
from datetime import datetime

import numpy as np
import sounddevice as sd

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ---------- CONFIG ----------
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
CHANNELS = 1
CALIBRATION_OFFSET = 95
GRAPH_POINTS = 150
ALERT_SUSTAIN_SECONDS = 2.0
ALERT_COOLDOWN_SECONDS = 5.0
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noise_log.csv")
DEFAULT_QUIET_MAX = 45.0
DEFAULT_MODERATE_MAX = 60.0


# ---------- WARDEN EMAIL ----------
HOSTEL_NAME = "A-Block"
ROOM_NO = "1"
WARDEN_EMAIL = "skbharath390@gmail.com"

SENDER_EMAIL = "sbharathk390@gmail.com"
SENDER_APP_PASSWORD = "mpfo xmli ualy gfei"  # Use an app password for Gmail



# ---------- DSP / HELPERS ----------
def rms_to_db(block: np.ndarray) -> float:
    rms = np.sqrt(np.mean(np.square(block)) + 1e-12)
    dbfs = 20 * np.log10(rms + 1e-9)
    approx_db = CALIBRATION_OFFSET + dbfs
    return max(0.0, approx_db)


def classify(db_value, quiet_max, moderate_max):
    if db_value <= quiet_max:
        return "QUIET"
    elif db_value <= moderate_max:
        return "MODERATE"
    else:
        return "NOISY"


def play_beep(duration=0.35, freq=1000, volume=0.5):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = np.sin(freq * t * 2 * np.pi) * volume
    fade = int(0.02 * SAMPLE_RATE)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    sd.play(tone.astype(np.float32), SAMPLE_RATE)


def ensure_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "noise_db", "status", "event"])


def log_event(db_value, status, event):
    ensure_log_file()
    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 f"{db_value:.1f}", status, event])


def send_warden_email(room_no, db_value):
    try:
        msg = EmailMessage()

        msg["Subject"] = f"Noise Alert - A-Block Room {room_no}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = WARDEN_EMAIL

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg.set_content(
            f"""NOISE ALERT

Hostel: {HOSTEL_NAME}
Room No: {room_no}
Noise Level: {db_value:.1f} dB
Status: NOISY
Time: {current_time}

The noise level has crossed the configured limit.
"""
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)

        print(f"Warden email sent for Room {room_no}")

    except Exception as e:
        print(f"Email error: {e}")


# ---------- GUI APP ----------
class NoiseMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Noise Level Monitor - Library / Study Zone")
        self.root.geometry("760x620")
        self.root.configure(bg="#f4f6f8")

        self.audio_q = queue.Queue()
        self.stream = None
        self.running = False
        self.history = deque([0.0] * GRAPH_POINTS, maxlen=GRAPH_POINTS)
        self.alert_count = 0
        self.noisy_since = None
        self.last_alert_time = 0.0

        self.quiet_max = tk.DoubleVar(value=DEFAULT_QUIET_MAX)
        self.moderate_max = tk.DoubleVar(value=DEFAULT_MODERATE_MAX)

        self._build_ui()
        ensure_log_file()
        self.root.after(100, self._refresh_ui)

    def _build_ui(self):
        tk.Label(self.root, text="📚 Study Zone Noise Monitor",
                 font=("Segoe UI", 18, "bold"), bg="#f4f6f8").pack(pady=(12, 4))

        self.db_label = tk.Label(self.root, text="0.0 dB",
                                  font=("Segoe UI", 40, "bold"), bg="#f4f6f8", fg="#2e7d32")
        self.db_label.pack(pady=4)

        self.status_label = tk.Label(self.root, text="STATUS: --",
                                      font=("Segoe UI", 16, "bold"), bg="#f4f6f8", fg="#333")
        self.status_label.pack(pady=(0, 8))

        self.fig = Figure(figsize=(7, 3), dpi=90)
        self.ax = self.fig.add_subplot(111)
        self.line, = self.ax.plot(range(GRAPH_POINTS), list(self.history), color="#1565c0")
        self.ax.set_ylim(0, 100)
        self.ax.set_xticks([])
        self.ax.set_ylabel("dB (approx)")
        self.ax.set_title("Live Noise Level")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(pady=6)

        cfg = tk.Frame(self.root, bg="#f4f6f8"); cfg.pack(pady=6)
        tk.Label(cfg, text="Quiet max (dB):", bg="#f4f6f8").grid(row=0, column=0, padx=4)
        tk.Entry(cfg, textvariable=self.quiet_max, width=6).grid(row=0, column=1, padx=4)
        tk.Label(cfg, text="Moderate max (dB):", bg="#f4f6f8").grid(row=0, column=2, padx=4)
        tk.Entry(cfg, textvariable=self.moderate_max, width=6).grid(row=0, column=3, padx=4)

        btns = tk.Frame(self.root, bg="#f4f6f8"); btns.pack(pady=10)
        self.start_btn = tk.Button(btns, text="▶ Start Monitoring", width=18,
                                    bg="#2e7d32", fg="white", command=self.start)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = tk.Button(btns, text="■ Stop", width=12,
                                   bg="#c62828", fg="white", command=self.stop, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=6)
        self.reset_btn = tk.Button(btns, text="Reset Alert Count", width=18,
                                    command=self.reset_alerts)
        self.reset_btn.grid(row=0, column=2, padx=6)

        self.alert_label = tk.Label(self.root, text="Alerts triggered: 0",
                                     font=("Segoe UI", 12), bg="#f4f6f8")
        self.alert_label.pack(pady=(4, 0))
        tk.Label(self.root, text=f"Log file: {LOG_FILE}",
                 font=("Segoe UI", 9), bg="#f4f6f8", fg="#666").pack(pady=(2, 10))

    def _audio_callback(self, indata, frames, time_info, status):
        self.audio_q.put(indata.copy())

    def start(self):
        if self.running:
            return
        try:
            self.stream = sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                          channels=CHANNELS, callback=self._audio_callback)
            self.stream.start()
        except Exception as e:
            messagebox.showerror("Microphone Error", f"Could not open microphone:\n{e}")
            return
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        log_event(0, "INFO", "Monitoring started")

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream = None
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        log_event(0, "INFO", "Monitoring stopped")

    def reset_alerts(self):
        self.alert_count = 0
        self.alert_label.config(text="Alerts triggered: 0")

    def _refresh_ui(self):
        latest_db = None
        while not self.audio_q.empty():
            block = self.audio_q.get_nowait()
            latest_db = rms_to_db(block[:, 0] if block.ndim > 1 else block)

        if latest_db is not None:
            self.history.append(latest_db)
            self._evaluate(latest_db)
            self._update_display(latest_db)
            self._update_graph()

        self.root.after(100, self._refresh_ui)

    def _update_display(self, db_value):
        status = classify(db_value, self.quiet_max.get(), self.moderate_max.get())
        colors = {"QUIET": "#2e7d32", "MODERATE": "#f9a825", "NOISY": "#c62828"}
        self.db_label.config(text=f"{db_value:.1f} dB", fg=colors[status])
        self.status_label.config(text=f"STATUS: {status}", fg=colors[status])

    def _update_graph(self):
        self.line.set_ydata(list(self.history))
        self.canvas.draw_idle()

    def _evaluate(self, db_value):
        status = classify(
            db_value,
            self.quiet_max.get(),
            self.moderate_max.get()
    )

    # Log when status changes
        if not hasattr(self, "last_status"):
            self.last_status = None

        if status != self.last_status:
            log_event(db_value, status, "Status changed")
            self.last_status = status

        if status == "NOISY":

            if self.noisy_since is None:
                self.noisy_since = time.time()

            sustained = time.time() - self.noisy_since

            if (
                sustained >= ALERT_SUSTAIN_SECONDS
                and not self.alert_sent_for_current_noise
            ):
                self._trigger_alert(db_value)
                self.alert_sent_for_current_noise = True

        else:
            # Noise returned below the limit.
            # Allow a new alert next time.
            self.noisy_since = None
            self.alert_sent_for_current_noise = False


    def _trigger_alert(self, db_value):
        self.alert_count += 1
        self.last_alert_time = time.time()

        self.alert_label.config(
            text=f"Alerts triggered: {self.alert_count}"
        )

        log_event(db_value, "NOISY", "ALERT")

        self._flash_screen()

        # Local warning beep
        threading.Thread(
            target=play_beep,
            daemon=True
        ).start()

        # Send ONE email
        threading.Thread(
            target=send_warden_email,
            args=(ROOM_NO, db_value),
            daemon=True
        ).start()


    def _flash_screen(self, times=4):
        def flash(n, on=True):
            if n <= 0:
                self.root.configure(bg="#f4f6f8"); return
            self.root.configure(bg="#ff8a80" if on else "#f4f6f8")
            self.root.after(150, lambda: flash(n - 1, not on))
        flash(times)


# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = NoiseMonitorApp(root)

    def on_close():
        app.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    