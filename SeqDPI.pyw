import ctypes
import math
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser

from seqdpi import APP_NAME, EngineLauncher, Health, QUICK_LINKS, UiLog, is_admin, is_windows, relaunch_as_admin

BG = "#120d20"
PANEL = "#1f1733"
PANEL_SOFT = "#2b2144"
INK = "#fff7df"
MUTED = "#b9acd4"
PINK = "#ff4fd8"
CYAN = "#39d9ff"
LIME = "#b8ff5c"
ORANGE = "#ff9f43"
VIOLET = "#8f6bff"
RED = "#ff5d73"


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


class AnimatedBackground(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg=BG, highlightthickness=0)
        self.t = 0
        self.bind("<Configure>", lambda _e: self.paint())
        self.after(33, self.tick)

    def tick(self):
        self.t += 1
        self.paint()
        self.after(33, self.tick)

    def paint(self):
        w, h = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        self.delete("bg")
        self.create_rectangle(0, 0, w, h, fill=BG, outline="", tags="bg")
        for i, color in enumerate((PINK, CYAN, VIOLET, LIME)):
            x = w * (0.18 + i * 0.22) + math.sin(self.t * 0.018 + i) * 42
            y = h * (0.25 + (i % 2) * 0.45) + math.cos(self.t * 0.014 + i) * 34
            r = 180 - i * 25
            self.glow(x, y, r, color)
        for x in range(-80, w + 80, 64):
            drift = math.sin(self.t * 0.02 + x * 0.01) * 14
            self.create_line(x + drift, 0, x - 120 + drift, h, fill="#261b3f", width=1, tags="bg")
        self.tag_lower("bg")

    def glow(self, x, y, r, color):
        for i in range(10, 0, -1):
            rr = r * i / 10
            shade = blend(color, BG, 0.74 + i * 0.022)
            self.create_oval(x - rr, y - rr, x + rr, y + rr, fill=shade, outline="", tags="bg")


class GlowButton(tk.Canvas):
    def __init__(self, master, text, command, color, width=150, height=48):
        super().__init__(master, width=width, height=height, bg=BG, highlightthickness=0, cursor="hand2")
        self.text, self.command, self.color = text, command, color
        self.disabled = False
        self.hover = False
        self.phase = 0
        self.bind("<Enter>", lambda _e: self.set_hover(True))
        self.bind("<Leave>", lambda _e: self.set_hover(False))
        self.bind("<Button-1>", lambda _e: None if self.disabled else self.command())
        self.after(45, self.tick)
        self.draw()

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def set_disabled(self, value):
        self.disabled = value
        self.draw()

    def tick(self):
        self.phase = (self.phase + 1) % 120
        self.draw()
        self.after(45, self.tick)

    def draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        color = "#4a405d" if self.disabled else self.color
        fill = blend(color, PANEL, 0.38 if self.hover else 0.58)
        self.round_rect(2, 2, w - 2, h - 2, 16, fill=fill, outline="")
        if not self.disabled:
            self.round_rect(1, 1, w - 1, h - 1, 16, outline=blend(color, INK, 0.25), width=2)
        self.create_text(w / 2, h / 2, text=self.text, fill=INK if not self.disabled else MUTED, font=("Segoe UI Semibold", 11))

    def round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)


class SeqDPIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.geometry("980x680")
        self.minsize(860, 620)
        self.configure(bg=BG)
        self.attributes("-alpha", 0.985)
        self.sound = SoundPlayer()
        self.logger = UiLog(self.append_log)
        self.engine = EngineLauncher(self.logger)
        self.health = Health(self.logger)
        self.busy = False
        self.status_text = tk.StringVar(value="hazırlanıyor")
        self.status_color = CYAN
        self.drag_x = 0
        self.drag_y = 0
        self.ring = 0
        self.build()
        self.center()
        self.after(250, lambda: self.sound.play("hello.mp3"))
        self.after(180, self.initial_check)
        self.after(33, self.animate)

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def build(self):
        self.bg = AnimatedBackground(self)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.shell = tk.Frame(self.bg, bg=BG)
        self.shell.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.90)
        self.titlebar = tk.Frame(self.shell, bg=BG, height=44)
        self.titlebar.pack(fill="x")
        self.titlebar.bind("<Button-1>", self.start_drag)
        self.titlebar.bind("<B1-Motion>", self.drag)
        tk.Label(self.titlebar, text="SeqDPI", bg=BG, fg=INK, font=("Segoe UI Black", 18)).pack(side="left")
        tk.Label(self.titlebar, text="transparent control bar", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(10, 0), pady=(5, 0))
        tk.Button(self.titlebar, text="✕", command=self.on_close, bg=BG, fg=RED, activebackground=BG, activeforeground=INK, relief="flat", font=("Segoe UI Semibold", 14), cursor="hand2").pack(side="right")
        tk.Button(self.titlebar, text="–", command=self.iconify_window, bg=BG, fg=MUTED, activebackground=BG, activeforeground=INK, relief="flat", font=("Segoe UI Semibold", 16), cursor="hand2").pack(side="right", padx=(0, 8))

        hero = tk.Frame(self.shell, bg=BG)
        hero.pack(fill="x", pady=(28, 0))
        self.power = tk.Canvas(hero, width=230, height=230, bg=BG, highlightthickness=0, cursor="hand2")
        self.power.pack(side="left", padx=(0, 34))
        self.power.bind("<Button-1>", lambda _e: self.enable() if not self.busy else None)
        right = tk.Frame(hero, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Tek tuş, temiz bağlantı.", bg=BG, fg=INK, font=("Segoe UI Semibold", 30)).pack(anchor="w")
        tk.Label(right, text="DNS sağlığı korunur, çalışan metod seçilir, kurulum ve kullanımda CMD yok.", bg=BG, fg=MUTED, font=("Segoe UI", 13), wraplength=580, justify="left").pack(anchor="w", pady=(10, 0))
        actions = tk.Frame(right, bg=BG)
        actions.pack(anchor="w", pady=(26, 0))
        self.buttons = [
            GlowButton(actions, "Erişimi aç", self.enable, PINK, 150),
            GlowButton(actions, "Sıradaki", self.next_method, CYAN, 130),
            GlowButton(actions, "Test", self.test, LIME, 104),
            GlowButton(actions, "Kapat", self.restore, ORANGE, 110),
        ]
        for b in self.buttons:
            b.pack(side="left", padx=(0, 12))
        links = tk.Frame(right, bg=BG)
        links.pack(anchor="w", pady=(16, 0))
        self.link(links, "Roblox", lambda: webbrowser.open(QUICK_LINKS["Roblox"]), PINK).pack(side="left", padx=(0, 10))
        self.link(links, "Discord", lambda: webbrowser.open(QUICK_LINKS["Discord"]), CYAN).pack(side="left")

        bottom = tk.Frame(self.shell, bg=BG)
        bottom.pack(fill="both", expand=True, pady=(26, 0))
        log_panel = tk.Frame(bottom, bg=PANEL, highlightthickness=1, highlightbackground="#49366d")
        log_panel.pack(side="left", fill="both", expand=True)
        tk.Label(log_panel, text="Canlı günlük", bg=PANEL, fg=INK, font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=18, pady=(14, 8))
        self.log_box = tk.Text(log_panel, bg="#171126", fg=INK, relief="flat", padx=18, pady=14, font=("Cascadia Mono", 10), wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")
        self.log_box.tag_config("ok", foreground=LIME)
        self.log_box.tag_config("fail", foreground=RED)
        self.log_box.tag_config("info", foreground=CYAN)
        side = tk.Frame(bottom, bg=BG, width=230)
        side.pack(side="right", fill="y", padx=(18, 0))
        self.status_canvas = tk.Canvas(side, width=210, height=118, bg=BG, highlightthickness=0)
        self.status_canvas.pack(fill="x", pady=(0, 16))
        self.metric(side, "DNS", "health gated", CYAN)
        self.metric(side, "Paket", "SeqDPI.exe", LIME)

    def link(self, master, text, cmd, color):
        return tk.Button(master, text=text, command=cmd, bg=PANEL_SOFT, fg=color, activebackground="#362855", activeforeground=INK, relief="flat", padx=16, pady=8, font=("Segoe UI Semibold", 10), cursor="hand2")

    def metric(self, master, title, value, color):
        f = tk.Frame(master, bg=PANEL, highlightthickness=1, highlightbackground="#49366d")
        f.pack(fill="x", pady=(0, 14))
        tk.Label(f, text=title, bg=PANEL, fg=color, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(f, text=value, bg=PANEL, fg=INK, font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=16, pady=(0, 14))

    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def drag(self, event):
        self.geometry(f"+{self.winfo_x() + event.x - self.drag_x}+{self.winfo_y() + event.y - self.drag_y}")

    def iconify_window(self):
        self.overrideredirect(False)
        self.iconify()
        self.after(200, lambda: self.overrideredirect(True))

    def initial_check(self):
        if not is_windows():
            self.set_status("windows gerekli", RED)
            self.logger("WinDivert ve netsh Windows gerektirir.")
            self.set_busy(True)
            return
        if not is_admin():
            self.set_status("admin gerekli", ORANGE)
            self.logger("Yönetici izni gerekiyor. Butona basınca UAC açılır.")
            self.buttons[0].text = "Admin aç"
            self.buttons[0].command = self.elevate
            return
        self.set_status("hazır", LIME)
        self.logger("Hazır. Minimal neon GUI aktif.")

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
        self.set_status("aktif", LIME)

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

        def worker():
            try:
                target()
            except Exception as exc:
                self.logger(f"Hata: {exc}")
                self.set_status("hata", RED)
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            finally:
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def set_busy(self, value):
        self.busy = value
        for b in self.buttons:
            b.set_disabled(value)

    def set_status(self, text, color):
        self.status_text.set(text)
        self.status_color = color

    def animate(self):
        self.ring = (self.ring + 5) % 360
        self.draw_power()
        self.draw_status()
        self.after(33, self.animate)

    def draw_power(self):
        c = self.power
        c.delete("all")
        pulse = 1 + math.sin(time.time() * 4) * 0.035
        cx = cy = 115
        for i, color in enumerate((PINK, CYAN, VIOLET, LIME)):
            r = (96 - i * 16) * pulse
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=3)
        c.create_oval(54, 54, 176, 176, fill="#201735", outline="#51406f", width=2)
        c.create_line(115, 76, 115, 116, fill=INK, width=9, capstyle="round")
        c.create_arc(82, 90, 148, 156, start=130, extent=280, outline=INK, width=9, style="arc")
        c.create_text(115, 198, text="TEK TUŞ", fill=MUTED, font=("Segoe UI Semibold", 10))

    def draw_status(self):
        c = self.status_canvas
        c.delete("all")
        c.create_oval(14, 14, 92, 92, outline="#3e315f", width=9)
        c.create_arc(14, 14, 92, 92, start=self.ring, extent=115, style="arc", outline=self.status_color, width=9)
        c.create_text(112, 42, text="DURUM", fill=MUTED, anchor="w", font=("Segoe UI Semibold", 8))
        c.create_text(112, 64, text=self.status_text.get(), fill=INK, anchor="w", font=("Segoe UI Semibold", 13))

    def append_log(self, message):
        def append():
            tag = "info"
            low = message.lower()
            if "ok" in low or "aktif" in low or "hazır" in low:
                tag = "ok"
            if "fail" in low or "hata" in low:
                tag = "fail"
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"• {message}\n", tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, append)

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
    SeqDPIApp().mainloop()
