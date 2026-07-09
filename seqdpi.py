import ctypes
import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import urlopen, Request

APP_NAME = "SeqDPI"
DNS_SERVERS = [
    "1.1.1.1",
    "1.0.0.1",
    "2606:4700:4700::1111",
    "2606:4700:4700::1001",
]
CHECK_HOSTS = ["roblox.com", "discord.com", "api.roblox.com", "gateway.discord.gg"]
QUICK_LINKS = {
    "Roblox": "https://www.roblox.com/",
    "Discord": "https://discord.com/app",
}


class Runner:
    def run(self, args, timeout=30):
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=startupinfo,
        )
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise RuntimeError(output or f"Komut başarısız: {args[0]}")
        return output

    def powershell(self, command, timeout=30):
        return self.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            timeout=timeout,
        )


class NetworkProfile:
    def __init__(self):
        self.runner = Runner()

    def adapters(self):
        command = (
            "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
            "Select-Object -ExpandProperty Name"
        )
        output = self.runner.powershell(command)
        names = [line.strip() for line in output.splitlines() if line.strip()]
        if not names:
            raise RuntimeError("Aktif ağ adaptörü bulamadım.")
        return names

    def enable(self):
        names = self.adapters()
        quoted_dns = ",".join(f"'{server}'" for server in DNS_SERVERS)
        for name in names:
            safe_name = name.replace("'", "''")
            command = (
                f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' "
                f"-ServerAddresses ({quoted_dns})"
            )
            self.runner.powershell(command)
        self.flush_dns()
        return names

    def restore(self):
        names = self.adapters()
        for name in names:
            safe_name = name.replace("'", "''")
            command = f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' -ResetServerAddresses"
            self.runner.powershell(command)
        self.flush_dns()
        return names

    def flush_dns(self):
        self.runner.run(["ipconfig", "/flushdns"])

    def resolve_report(self):
        results = []
        for host in CHECK_HOSTS:
            try:
                socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
                results.append((host, True))
            except socket.gaierror:
                results.append((host, False))
        return results

    def http_probe(self):
        request = Request("https://www.roblox.com/", headers={"User-Agent": APP_NAME})
        try:
            with urlopen(request, timeout=8) as response:
                return 200 <= response.status < 500
        except Exception:
            return False


def is_windows():
    return os.name == "nt"


def is_admin():
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{arg}"' for arg in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


class SeqDPIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.profile = NetworkProfile()
        self.configure_app()
        self.build_ui()
        self.after(250, self.initial_check)

    def configure_app(self):
        self.title(APP_NAME)
        self.geometry("720x520")
        self.minsize(640, 480)
        self.configure(bg="#f7f5ef")
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f7f5ef")
        style.configure("Muted.TLabel", background="#f7f5ef", foreground="#6f685f", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f7f5ef", foreground="#211d18", font=("Segoe UI Semibold", 24))
        style.configure("Body.TLabel", background="#f7f5ef", foreground="#3a342d", font=("Segoe UI", 11))
        style.configure("Status.TLabel", background="#efe8dd", foreground="#2b261f", font=("Segoe UI Semibold", 11), padding=12)
        style.configure("Action.TButton", font=("Segoe UI Semibold", 14), padding=(22, 14))
        style.configure("Ghost.TButton", font=("Segoe UI", 10), padding=(14, 9))

    def build_ui(self):
        shell = ttk.Frame(self, padding=(34, 30, 34, 26))
        shell.pack(fill="both", expand=True)

        eyebrow = ttk.Label(shell, text="WINDOWS DNS PROFİLİ", style="Muted.TLabel")
        eyebrow.pack(anchor="w")

        title = ttk.Label(shell, text="Tek tuşla erişim profili", style="Title.TLabel")
        title.pack(anchor="w", pady=(6, 0))

        body = ttk.Label(
            shell,
            text="Roblox ve Discord için DNS profilini Cloudflare üstüne alır, önbelleği temizler, sonra bağlantıyı kontrol eder.",
            style="Body.TLabel",
            wraplength=620,
        )
        body.pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))

        self.main_button = ttk.Button(actions, text="Engeli aç", style="Action.TButton", command=self.enable_profile)
        self.main_button.pack(side="left")

        self.restore_button = ttk.Button(actions, text="DNS'i geri al", style="Ghost.TButton", command=self.restore_profile)
        self.restore_button.pack(side="left", padx=(12, 0))

        self.roblox_button = ttk.Button(actions, text="Roblox", style="Ghost.TButton", command=lambda: self.open_link("Roblox"))
        self.roblox_button.pack(side="right", padx=(8, 0))

        self.discord_button = ttk.Button(actions, text="Discord", style="Ghost.TButton", command=lambda: self.open_link("Discord"))
        self.discord_button.pack(side="right")

        self.status = ttk.Label(shell, text="Hazırlanıyor", style="Status.TLabel")
        self.status.pack(fill="x", pady=(0, 18))

        log_label = ttk.Label(shell, text="İşlem günlüğü", style="Muted.TLabel")
        log_label.pack(anchor="w", pady=(0, 8))

        log_frame = tk.Frame(shell, bg="#2b261f", highlightthickness=0)
        log_frame.pack(fill="both", expand=True)

        self.log_box = tk.Text(
            log_frame,
            bg="#2b261f",
            fg="#f3ede3",
            insertbackground="#f3ede3",
            relief="flat",
            padx=18,
            pady=16,
            font=("Cascadia Mono", 10),
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def initial_check(self):
        if not is_windows():
            self.set_busy(False)
            self.status.configure(text="Bu sürüm Windows için hazırlandı.")
            self.log("Windows dışında sistem DNS ayarı yapmam. Kod tarafı güvenli kalsın diye böyle.")
            self.main_button.configure(state="disabled")
            self.restore_button.configure(state="disabled")
            return

        if not is_admin():
            self.status.configure(text="Yönetici izni gerekiyor.")
            self.log("DNS ayarı için yönetici izni lazım. Butona basınca UAC penceresi açılacak.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return

        self.status.configure(text="Hazır. Butona bas, DNS profili aktif olsun.")
        self.log("Yönetici izni tamam. Aktif ağ adaptörlerini değiştirebilirim.")

    def elevate(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Yönetici olarak açılamadı:\n{exc}")

    def run_background(self, target):
        self.set_busy(True)
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def enable_profile(self):
        if not is_admin():
            self.elevate()
            return

        def work():
            try:
                self.safe_status("DNS profili uygulanıyor")
                adapters = self.profile.enable()
                self.log(f"DNS ayarlandı: {', '.join(adapters)}")
                self.log("DNS önbelleği temizlendi.")
                self.check_connectivity()
            except Exception as exc:
                self.safe_status("İşlem başarısız")
                self.log(f"Hata: {exc}")
                messagebox.showerror(APP_NAME, str(exc))
            finally:
                self.set_busy(False)

        self.run_background(work)

    def restore_profile(self):
        def work():
            try:
                self.safe_status("DNS ayarı geri alınıyor")
                adapters = self.profile.restore()
                self.log(f"Otomatik DNS'e dönüldü: {', '.join(adapters)}")
                self.safe_status("Geri alındı. Eski ağ profilindesin.")
            except Exception as exc:
                self.safe_status("Geri alma başarısız")
                self.log(f"Hata: {exc}")
                messagebox.showerror(APP_NAME, str(exc))
            finally:
                self.set_busy(False)

        self.run_background(work)

    def check_connectivity(self):
        self.safe_status("Roblox ve Discord kontrol ediliyor")
        report = self.profile.resolve_report()
        for host, ok in report:
            self.log(f"{'OK' if ok else 'FAIL'}  {host}")
        if self.profile.http_probe():
            self.log("OK  roblox web yanıt verdi")
            self.safe_status("Bitti. Roblox ve Discord'u deneyebilirsin.")
        else:
            self.log("Uyarı: Roblox web testi yanıt vermedi. DNS dışı engel varsa bu tek başına yetmeyebilir.")
            self.safe_status("DNS profili aktif, ama bağlantı testi net değil.")

    def open_link(self, name):
        import webbrowser

        webbrowser.open(QUICK_LINKS[name])

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.main_button.configure(state=state)
        self.restore_button.configure(state=state)

    def safe_status(self, text):
        self.after(0, lambda: self.status.configure(text=text))

    def log(self, message):
        def append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"• {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, append)


if __name__ == "__main__":
    app = SeqDPIApp()
    app.mainloop()
