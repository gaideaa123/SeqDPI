import ctypes
import math
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser

from seqdpi import (
    APP_NAME,
    EngineLauncher,
    Health,
    QUICK_LINKS,
    UiLog,
    is_admin,
    is_windows,
    relaunch_as_admin,
)

BG = "#130f22"
INK = "#fff7df"
MUTED = "#b9acd4"
PINK = "#ff4fd8"
CYAN = "#39d9ff"
LIME = "#b8ff5c"
ORANGE = "#ff9f43"
VIOLET = "#8f6bff"
RED = "#ff5d73"
PANEL = "#211936"
PANEL_2 = "#2c2145"


def resource_path(name):
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)
    roots.extend([os.path.dirname(os.path.abspath(__file__)), os.getcwd()])
    for root in roots:
        path = os.path.join(root, name)
        if os.path.exists(path):
            return path
    return None


class SoundPlayer:
    def __init__(self):
        self.counter = 0

    def play(self, filename):
        path = resource_path(filename)
        if not path or os.name != "nt":
            return
        self.counter += 1
        alias = f"seqdpi_sound_{self.counter}"
        safe = path.replace('"', '')

        def worker():
            try:
                winmm = ctypes.windll.winmm
                winmm.mciSendStringW(f'open "{safe}" type mpegvideo alias {alias}', None, 0, None)
                winmm.mciSendStringW(f'play {alias}', None, 0, None)
                time.sleep(8)
                winmm.mciSendStringW(f'close {alias}', None, 0, None)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()


class NeonCanvas(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, highlightthickness=0, bg=BG)
        self.t = 0.0
        self.orbs = [
            {"x": 0.18, "y": 0.22, "r": 150, "c": PINK, "s": 0.011, "p": 0.0},
            {"x": 0.82, "y": 0.18, "r": 120, "c": CYAN, "s": 0.014, "p": 2.1},
            {"x": 0.74, "y": 0.78, "r": 170, "c": VIOLET, "s": 0.009, "p": 4.2},
            {"x": 0.25, "y": 0.82, "r": 95, "c": LIME, "s": 0.017, "p": 1.4},
        ]
        self.bind("<Configure>", lambda _event: self.paint())
        self.after(16, self.animate)

    def animate(self):
        self.t += 1.0
        self.paint()
        self.after(33, self.animate)

    def paint(self):
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        self.delete("bg")
        self.create_rectangle(0, 0, w, h, fill=BG, outline="", tags="bg")
        for i in range(0, w, 54):
            drift = math.sin((self.t * 0.018) + i * 0.02) * 10
            self.create_line(i + drift, 0, i - 80 + drift, h, fill="#241a3d", width=1, tags="bg")
        for orb in self.orbs:
            wobble = math.sin(self.t * orb["s"] + orb["p"])
            x = w * orb["x"] + math.cos(self.t * orb["s"] + orb["p"]) * 34
            y = h * orb["y"] + wobble * 28
            r = orb["r"] + wobble * 16
            self.draw_glow(x, y, r, orb["c"])
        for n in range(18):
            x = (n * 97 + self.t * 0.9) % (w + 120) - 60
            y = 58 + (n * 43) % max(h - 80, 1)
            self.create_oval(x, y, x + 3, y + 3, fill="#f8e8ff", outline="", tags="bg")
        self.tag_lower("bg")

    def draw_glow(self, x, y, r, color):
        for i in range(12, 0, -1):
            ratio = i / 12
            rr = r * ratio
            shade = blend(color, BG, 0.68 + ratio * 0.28)
            self.create_oval(x - rr, y - rr, x + rr, y + rr, fill=shade, outline="", tags="bg")


class NeonButton(tk.Canvas):
    def __init__(self, master, text, command, fill=PINK, width=178, height=52):
        super().__init__(master, width=width, height=height, bg=BG, highlightthickness=0, cursor="hand2")
        self.text = text
        self.command = command
        self.fill = fill
        self.hover = False
        self.disabled = False
        self.pulse = 0
        self.bind("<Enter>", self.enter)
        self.bind("<Leave>", self.leave)
        self.bind("<Button-1>", self.click)
        self.after(40, self.tick)
        self.draw()

    def set_disabled(self, value):
        self.disabled = value
        self.draw()

    def enter(self, _event):
        self.hover = True
        self.draw()

    def leave(self, _event):
        self.hover = False
        self.draw()

    def click(self, _event):
        if not self.disabled and self.command:
            self.command()

    def tick(self):
        self.pulse = (self.pulse + 1) % 120
        self.draw()
        self.after(40, self.tick)

    def draw(self):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        base = "#403650" if self.disabled else self.fill
        glow = 4 + math.sin(self.pulse / 120 * math.tau) * 3
        if not self.disabled:
            self.round_rect(2, 2, w - 2, h - 2, 18, fill=blend(base, "#fff7df", 0.12 if self.hover else 0.0), outline="")
            self.round_rect(1, 1, w - 1, h - 1, 18, outline=blend(base, "#fff7df", 0.35), width=max(2, int(glow / 2)))
        else:
            self.round_rect(2, 2, w - 2, h - 2, 18, fill=base, outline="#5b526a", width=1)
        self.create_text(w / 2, h / 2, text=self.text, fill=INK if not self.disabled else "#9d93ad", font=("Segoe UI Semibold", 12))

    def round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)


class SeqDPINeonApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x720")
        self.minsize(860, 620)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.sound = SoundPlayer()
        self.logger = UiLog(self.append_log)
        self.engine = EngineLauncher(self.logger)
        self.health = Health(self.logger)
        self.status_text = tk.StringVar(value="hazırlanıyor")
        self.status_color = CYAN
        self.busy = False
        self.ring_angle = 0
        self.build()
        self.after(300, lambda: self.sound.play("hello.mp3"))
        self.after(180, self.initial_check)
        self.after(40, self.animate_status)

    def build(self):
        self.bg = NeonCanvas(self)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.main = tk.Frame(self.bg, bg=BG)
        self.main.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.88)
        top = tk.Frame(self.main, bg=BG)
        top.pack(fill="x")
        brand = tk.Frame(top, bg=BG)
        brand.pack(side="left", anchor="n")
        tk.Label(brand, text="SeqDPI", bg=BG, fg=INK, font=("Segoe UI Black", 34)).pack(anchor="w")
        tk.Label(brand, text="renkli, sessiz, tek tuş", bg=BG, fg=MUTED, font=("Segoe UI", 12)).pack(anchor="w", pady=(2, 0))
        self.status_canvas = tk.Canvas(top, width=190, height=86, bg=BG, highlightthickness=0)
        self.status_canvas.pack(side="right", anchor="ne")
        hero = tk.Frame(self.main, bg=BG)
        hero.pack(fill="x", pady=(34, 0))
        self.power = tk.Canvas(hero, width=260, height=260, bg=BG, highlightthickness=0)
        self.power.pack(side="left", padx=(0, 34))
        self.power.bind("<Button-1>", lambda _event: self.enable() if not self.busy else None)
        self.power.bind("<Enter>", lambda _event: self.power.configure(cursor="hand2"))
        copy = tk.Frame(hero, bg=BG)
        copy.pack(side="left", fill="both", expand=True)
        tk.Label(copy, text="Engeli aç, gerisini sakince bana bırak.", bg=BG, fg=INK, font=("Segoe UI Semibold", 26), wraplength=560, justify="left").pack(anchor="w")
        tk.Label(copy, text="DNS sağlığı kontrol edilir, çalışan metod korunur, CMD penceresi gösterilmez. Olmazsa sıradaki yöntem tek tık uzakta.", bg=BG, fg=MUTED, font=("Segoe UI", 13), wraplength=600, justify="left").pack(anchor="w", pady=(12, 0))
        actions = tk.Frame(copy, bg=BG)
        actions.pack(anchor="w", pady=(28, 0))
        self.btn_enable = NeonButton(actions, "Erişimi aç", self.enable, PINK, 164)
        self.btn_enable.pack(side="left", padx=(0, 12))
        self.btn_next = NeonButton(actions, "Sıradaki", self.next_method, CYAN, 132)
        self.btn_next.pack(side="left", padx=(0, 12))
        self.btn_test = NeonButton(actions, "Test", self.test, LIME, 112)
        self.btn_test.pack(side="left", padx=(0, 12))
        self.btn_restore = NeonButton(actions, "Kapat", self.restore, ORANGE, 118)
        self.btn_restore.pack(side="left")
        links = tk.Frame(copy, bg=BG)
        links.pack(anchor="w", pady=(18, 0))
        self.link_button(links, "Roblox", lambda: self.open_link("Roblox"), PINK).pack(side="left", padx=(0, 10))
        self.link_button(links, "Discord", lambda: self.open_link("Discord"), CYAN).pack(side="left")
        lower = tk.Frame(self.main, bg=BG)
        lower.pack(fill="both", expand=True, pady=(30, 0))
        self.log_frame = tk.Frame(lower, bg=PANEL, highlightthickness=1, highlightbackground="#4c3b74")
        self.log_frame.pack(side="left", fill="both", expand=True)
        tk.Label(self.log_frame, text="Canlı günlük", bg=PANEL, fg=INK, font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=18, pady=(14, 8))
        self.log_box = tk.Text(self.log_frame, bg="#171126", fg="#f9ecff", insertbackground=INK, relief="flat", padx=18, pady=14, height=11, font=("Cascadia Mono", 10), wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")
        self.log_box.tag_config("ok", foreground=LIME)
        self.log_box.tag_config("fail", foreground=RED)
        self.log_box.tag_config("info", foreground=CYAN)
        side = tk.Frame(lower, bg=BG, width=250)
        side.pack(side="right", fill="y", padx=(20, 0))
        self.metric(side, "DNS", "health gated", CYAN)
        self.metric(side, "Mod", "auto fallback", PINK)
        self.metric(side, "Paket", "SeqDPI.exe", LIME)

    def link_button(self, master, text, command, color):
        return tk.Button(master, text=text, command=command, bg=PANEL_2, fg=color, activebackground="#362855", activeforeground=INK, relief="flat", padx=16, pady=8, font=("Segoe UI Semibold", 10), cursor="hand2")

    def metric(self, master, title, value, color):
        frame = tk.Frame(master, bg=PANEL, highlightthickness=1, highlightbackground="#4c3b74")
        frame.pack(fill="x", pady=(0, 14))
        tk.Label(frame, text=title.upper(), bg=PANEL, fg=color, font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(frame, text=value, bg=PANEL, fg=INK, font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=16, pady=(0, 14))

    def initial_check(self):
        if not is_windows():
            self.set_status("windows gerekli", RED)
            self.logger("WinDivert ve netsh Windows gerektirir.")
            self.set_busy(True)
            return
        if not is_admin():
            self.set_status("admin gerekli", ORANGE)
            self.logger("Yönetici izni gerekiyor. Butona basınca UAC açılır.")
            self.btn_enable.text = "Admin aç"
            self.btn_enable.command = self.elevate
            self.btn_enable.draw()
            return
        self.set_status("hazır", LIME)
        self.logger("Hazır. Sesler paketlendi, neon GUI aktif.")

    def elevate(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def enable(self):
        self.run_job("açılıyor", PINK, self.enable_work)

    def enable_work(self):
        method = self.engine.start()
        self.logger(f"Aktif yöntem: {method.name}")
        self.health.full_report()
        self.sound.play("dns.mp3")
        self.set_status("aktif", LIME)

    def next_method(self):
        self.run_job("alternatif", CYAN, self.next_work)

    def next_work(self):
        method = self.engine.next()
        self.logger(f"Aktif yöntem: {method.name}")
        self.health.full_report()
        self.sound.play("dns.mp3")
        self.set_status("alternatif aktif", LIME)

    def test(self):
        self.run_job("test", VIOLET, self.health.full_report)

    def restore(self):
        self.run_job("kapatılıyor", ORANGE, self.restore_work)

    def restore_work(self):
        self.engine.stop_all()
        self.set_status("kapalı", ORANGE)
        self.logger("Motor durdu, DNS ve firewall ayarları geri alındı.")

    def run_job(self, status, color, target):
        if self.busy:
            return
        self.set_busy(True)
        self.set_status(status, color)

        def work():
            try:
                target()
            except Exception as exc:
                self.logger(f"Hata: {exc}")
                self.set_status("hata", RED)
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            finally:
                self.set_busy(False)

        threading.Thread(target=work, daemon=True).start()

    def set_busy(self, value):
        self.busy = value
        for button in (self.btn_enable, self.btn_next, self.btn_test, self.btn_restore):
            button.set_disabled(value)

    def set_status(self, text, color):
        self.status_text.set(text)
        self.status_color = color

    def animate_status(self):
        self.ring_angle = (self.ring_angle + 5) % 360
        self.draw_status()
        self.draw_power()
        self.after(33, self.animate_status)

    def draw_status(self):
        c = self.status_canvas
        c.delete("all")
        c.create_oval(12, 12, 74, 74, outline="#3e315f", width=8)
        c.create_arc(12, 12, 74, 74, start=self.ring_angle, extent=110, style="arc", outline=self.status_color, width=8)
        c.create_text(104, 32, text="DURUM", fill=MUTED, anchor="w", font=("Segoe UI Semibold", 8))
        c.create_text(104, 54, text=self.status_text.get(), fill=INK, anchor="w", font=("Segoe UI Semibold", 13))

    def draw_power(self):
        c = self.power
        c.delete("all")
        pulse = 1 + math.sin(time.time() * 4) * 0.04
        cx = cy = 130
        for i, color in enumerate((PINK, CYAN, VIOLET, LIME)):
            r = (106 - i * 18) * pulse
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=3)
        c.create_oval(58, 58, 202, 202, fill="#201735", outline="#4f3d74", width=2)
        c.create_line(130, 82, 130, 130, fill=INK, width=10, capstyle="round")
        c.create_arc(92, 98, 168, 174, start=130, extent=280, outline=INK, width=10, style="arc")
        c.create_text(130, 215, text="TEK TUŞ", fill=MUTED, font=("Segoe UI Semibold", 10))

    def append_log(self, message):
        def append():
            tag = "info"
            if "OK" in message or "aktif" in message.lower() or "Hazır" in message:
                tag = "ok"
            if "FAIL" in message or "Hata" in message or "hata" in message.lower():
                tag = "fail"
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"• {message}\n", tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, append)

    def open_link(self, name):
        webbrowser.open(QUICK_LINKS[name])

    def on_close(self):
        if messagebox.askyesno(APP_NAME, "Kapatırken motoru durdurup ayarları geri alayım mı?"):
            try:
                self.engine.stop_all()
            except Exception:
                pass
        self.destroy()


def blend(a, b, t):
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex(int(ar * (1 - t) + br * t), int(ag * (1 - t) + bg * t), int(ab * (1 - t) + bb * t))


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


if __name__ == "__main__":
    SeqDPINeonApp().mainloop()
