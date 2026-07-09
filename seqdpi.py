import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "SeqDPI"
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
ENGINE_DIR = APP_DIR / "engine"
DOWNLOAD_ZIP = APP_DIR / "goodbyedpi-turkey.zip"
DNS_SERVERS = ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]
CHECK_HOSTS = ["roblox.com", "auth.roblox.com", "games.roblox.com", "discord.com", "gateway.discord.gg", "wikipedia.org"]
QUICK_LINKS = {"Roblox": "https://www.roblox.com/", "Discord": "https://discord.com/app"}
QUIC_RULE = "SeqDPI Block QUIC HTTP3"

# The important bit from the research: DNS changing is not enough, and plain -9 can still lose
# when the ISP poisons/intercepts DNS. These presets use GoodbyeDPI's own DNS redirection to a
# resolver running on a non-standard port, then block QUIC/HTTP3 so browsers fall back to TCP where
# WinDivert packet tricks apply.
DNS_REDIR = ["--dns-addr", "77.88.8.8", "--dns-port", "1253", "--dnsv6-addr", "2a02:6b8::feed:0ff", "--dnsv6-port", "1253"]
GOODBYEDPI_PRESETS = [
    ("Türkiye DNS redir", ["-9", *DNS_REDIR]),
    ("SNI parçalama", ["-f", "2", "-e", "2", "--wrong-seq", "--wrong-chksum", "--reverse-frag", "--frag-by-sni", "--max-payload", "-q", *DNS_REDIR]),
    ("Uyumlu mod", ["-7", *DNS_REDIR]),
    ("Eski uyumlu mod", ["-2", *DNS_REDIR]),
]


class Runner:
    def run(self, args, timeout=40, check=True):
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, startupinfo=startupinfo)
        output = (completed.stdout + completed.stderr).strip()
        if check and completed.returncode != 0:
            raise RuntimeError(output or f"Komut başarısız: {args[0]}")
        return output

    def powershell(self, command, timeout=40, check=True):
        return self.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=timeout, check=check)


class EngineManager:
    def __init__(self, log):
        self.log = log

    def exe_path(self):
        candidates = list(ENGINE_DIR.rglob("goodbyedpi.exe"))
        if not candidates:
            return None
        x64 = [path for path in candidates if "x86_64" in str(path).lower() or "x64" in str(path).lower()]
        return x64[0] if x64 else candidates[0]

    def ensure(self):
        existing = self.exe_path()
        if existing:
            return existing
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.log("Türkiye fork motoru indiriliyor, ilk kurulum biraz sürebilir.")
        release = self.github_json("https://api.github.com/repos/cagritaskn/GoodbyeDPI-Turkey/releases/latest")
        asset_url = self.pick_release_zip(release)
        self.download(asset_url, DOWNLOAD_ZIP)
        if ENGINE_DIR.exists():
            shutil.rmtree(ENGINE_DIR)
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(DOWNLOAD_ZIP) as archive:
            archive.extractall(ENGINE_DIR)
        exe = self.exe_path()
        if not exe:
            raise RuntimeError("goodbyedpi.exe indirilen pakette bulunamadı.")
        self.log(f"Motor hazır: {exe.parent.name}")
        return exe

    def github_json(self, url):
        request = Request(url, headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def pick_release_zip(self, release):
        for asset in release.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and "source" not in name:
                return asset["browser_download_url"]
        raise RuntimeError("GoodbyeDPI Turkey release zip dosyası bulunamadı.")

    def download(self, url, target):
        request = Request(url, headers={"User-Agent": APP_NAME})
        with urlopen(request, timeout=60) as response, target.open("wb") as file:
            shutil.copyfileobj(response, file)


class WindowsTweaks:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def apply(self):
        self.block_quic()
        self.disable_chromium_kyber()

    def restore(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.log("QUIC/HTTP3 engeli kaldırıldı.")

    def block_quic(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.runner.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={QUIC_RULE}", "dir=out", "action=block", "protocol=UDP", "remoteport=443",
        ])
        self.log("QUIC/HTTP3 kapatıldı. Tarayıcılar TCP'ye düşecek.")

    def disable_chromium_kyber(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "PostQuantumKeyAgreementEnabled", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
            except PermissionError:
                self.log("Chrome/Edge Kyber policy yazılamadı. Yönetici iznini kontrol et.")
                return
        self.log("Chrome/Edge Kyber kapatıldı. Şişen ClientHello sorunu devre dışı.")


class NetworkProfile:
    def __init__(self, log):
        self.runner = Runner()
        self.engine = EngineManager(log)
        self.tweaks = WindowsTweaks(self.runner, log)
        self.process = None
        self.active_preset_index = 0
        self.log = log

    def adapters(self):
        command = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"
        output = self.runner.powershell(command)
        names = [line.strip() for line in output.splitlines() if line.strip()]
        if not names:
            raise RuntimeError("Aktif ağ adaptörü bulamadım.")
        return names

    def enable_dns(self):
        names = self.adapters()
        quoted_dns = ",".join(f"'{server}'" for server in DNS_SERVERS)
        for name in names:
            safe_name = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' -ServerAddresses ({quoted_dns})")
        self.runner.run(["ipconfig", "/flushdns"])
        return names

    def restore_dns(self):
        names = self.adapters()
        for name in names:
            safe_name = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' -ResetServerAddresses")
        self.runner.run(["ipconfig", "/flushdns"])
        return names

    def enable(self, preset_index=0):
        adapters = self.enable_dns()
        self.tweaks.apply()
        exe = self.engine.ensure()
        self.stop_engine()
        self.active_preset_index = preset_index
        label, args = GOODBYEDPI_PRESETS[preset_index]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = subprocess.Popen([str(exe), *args], cwd=str(exe.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        time.sleep(1.2)
        if self.process.poll() is not None:
            raise RuntimeError("GoodbyeDPI motoru başladıktan hemen sonra kapandı.")
        return adapters, label, " ".join(args)

    def try_next_preset(self):
        next_index = (self.active_preset_index + 1) % len(GOODBYEDPI_PRESETS)
        return self.enable(next_index)

    def stop_engine(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def restore(self):
        self.stop_engine()
        self.tweaks.restore()
        return self.restore_dns()

    def resolve_report(self):
        results = []
        for host in CHECK_HOSTS:
            try:
                socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
                results.append((host, True))
            except socket.gaierror:
                results.append((host, False))
        return results

    def probe(self, url):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 SeqDPI"})
            with urlopen(request, timeout=12) as response:
                return response.status < 500, f"HTTP {response.status}"
        except HTTPError as exc:
            return exc.code < 500, f"HTTP {exc.code}"
        except URLError as exc:
            return False, str(exc.reason)
        except Exception as exc:
            return False, str(exc)


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
        self.profile = NetworkProfile(self.log)
        self.configure_app()
        self.build_ui()
        self.after(250, self.initial_check)

    def configure_app(self):
        self.title(APP_NAME)
        self.geometry("800x590")
        self.minsize(700, 530)
        self.configure(bg="#f7f5ef")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
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
        ttk.Label(shell, text="TÜRKİYE DNS REDIR + WINDIVERT", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(shell, text="DNS zehrini de, QUIC kaçışını da kapatır", style="Title.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(shell, text="GoodbyeDPI Turkey motorunu kullanır, DNS isteklerini non-standard porta yönlendirir, UDP 443/HTTP3'ü keser ve Chrome/Edge Kyber ClientHello şişmesini kapatır.", style="Body.TLabel", wraplength=700).pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))
        self.main_button = ttk.Button(actions, text="Erişim engelini aç", style="Action.TButton", command=self.enable_profile)
        self.main_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="Alternatif modu dene", style="Ghost.TButton", command=self.try_next)
        self.next_button.pack(side="left", padx=(12, 0))
        self.restore_button = ttk.Button(actions, text="Tamamen kapat", style="Ghost.TButton", command=self.restore_profile)
        self.restore_button.pack(side="left", padx=(12, 0))
        ttk.Button(actions, text="Roblox", style="Ghost.TButton", command=lambda: self.open_link("Roblox")).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Discord", style="Ghost.TButton", command=lambda: self.open_link("Discord")).pack(side="right")

        self.status = ttk.Label(shell, text="Hazırlanıyor", style="Status.TLabel")
        self.status.pack(fill="x", pady=(0, 18))
        ttk.Label(shell, text="İşlem günlüğü", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        log_frame = tk.Frame(shell, bg="#2b261f", highlightthickness=0)
        log_frame.pack(fill="both", expand=True)
        self.log_box = tk.Text(log_frame, bg="#2b261f", fg="#f3ede3", insertbackground="#f3ede3", relief="flat", padx=18, pady=16, font=("Cascadia Mono", 10), wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def initial_check(self):
        if not is_windows():
            self.status.configure(text="Bu sürüm Windows için.")
            self.log("WinDivert yalnız Windows tarafında çalışır.")
            self.main_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
            self.restore_button.configure(state="disabled")
            return
        if not is_admin():
            self.status.configure(text="Yönetici izni gerekiyor.")
            self.log("WinDivert, firewall ve DNS ayarı için yönetici izni şart.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return
        self.status.configure(text="Hazır. Türkiye DNS redir modu açılacak.")
        self.log("Yönetici izni tamam. Proxy değil, paket seviyesinde mod açılacak.")

    def elevate(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Yönetici olarak açılamadı:\n{exc}")

    def enable_profile(self):
        self.run_background(lambda: self.enable_with_preset(0))

    def try_next(self):
        self.run_background(self.enable_next)

    def enable_with_preset(self, index):
        try:
            self.safe_status("Sistem modu açılıyor")
            adapters, label, args = self.profile.enable(index)
            self.log(f"DNS ayarlandı: {', '.join(adapters)}")
            self.log(f"GoodbyeDPI çalışıyor: {label} ({args})")
            self.check_connectivity()
        except Exception as exc:
            self.safe_status("İşlem başarısız")
            self.log(f"Hata: {exc}")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def enable_next(self):
        try:
            self.safe_status("Alternatif mod deneniyor")
            adapters, label, args = self.profile.try_next_preset()
            self.log(f"Alternatif aktif: {label} ({args})")
            self.check_connectivity()
        except Exception as exc:
            self.safe_status("Alternatif mod başarısız")
            self.log(f"Hata: {exc}")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def restore_profile(self):
        def work():
            try:
                self.safe_status("Kapatılıyor")
                adapters = self.profile.restore()
                self.log(f"GoodbyeDPI kapandı, DNS otomatiğe döndü: {', '.join(adapters)}")
                self.safe_status("Kapandı. Eski ağ profilindesin.")
            except Exception as exc:
                self.safe_status("Kapatma başarısız")
                self.log(f"Hata: {exc}")
                messagebox.showerror(APP_NAME, str(exc))
            finally:
                self.set_busy(False)
        self.run_background(work)

    def check_connectivity(self):
        self.safe_status("Bağlantılar kontrol ediliyor")
        for host, ok in self.profile.resolve_report():
            self.log(f"{'OK' if ok else 'FAIL'}  {host}")
        for name, url in (("Roblox web testi", "https://www.roblox.com/"), ("Discord web testi", "https://discord.com/")):
            ok, detail = self.profile.probe(url)
            self.log(f"{'OK' if ok else 'FAIL'}  {name} ({detail})")
        self.safe_status("Aktif. Olmazsa 'Alternatif modu dene' butonuna bas.")

    def run_background(self, target):
        self.set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def open_link(self, name):
        import webbrowser
        webbrowser.open(QUICK_LINKS[name])

    def on_close(self):
        if messagebox.askyesno(APP_NAME, "Kapatırken motoru durdurup DNS/firewall ayarlarını geri alayım mı?"):
            try:
                self.profile.restore()
            except Exception:
                pass
        self.destroy()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for button in (self.main_button, self.next_button, self.restore_button):
            button.configure(state=state)

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
