import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import zipfile
from dataclasses import dataclass
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
STATE_FILE = APP_DIR / "state.json"
LOG_FILE = APP_DIR / "seqdpi.log"
QUIC_RULE = "SeqDPI Block QUIC HTTP3"
CHECK_HOSTS = [
    "roblox.com",
    "www.roblox.com",
    "auth.roblox.com",
    "games.roblox.com",
    "discord.com",
    "gateway.discord.gg",
    "wikipedia.org",
]
CHECK_URLS = [
    ("Roblox", "https://www.roblox.com/"),
    ("Roblox auth", "https://auth.roblox.com/"),
    ("Discord", "https://discord.com/"),
    ("Discord gateway", "https://gateway.discord.gg/"),
]
DNS_SERVERS = ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]
QUICK_LINKS = {"Roblox": "https://www.roblox.com/", "Discord": "https://discord.com/app"}

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


@dataclass
class Method:
    name: str
    kind: str
    command: list[str]
    cwd: Path
    service_like: bool = False
    score: int = 0


class AppLog:
    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        APP_DIR.mkdir(parents=True, exist_ok=True)

    def __call__(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass
        self.ui_callback(message)


class Runner:
    def run(self, args, timeout=60, check=True, cwd=None):
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = CREATE_NO_WINDOW
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
            cwd=str(cwd) if cwd else None,
        )
        output = (completed.stdout + completed.stderr).strip()
        if check and completed.returncode != 0:
            raise RuntimeError(output or f"Komut başarısız: {args[0]}")
        return completed.returncode, output

    def powershell(self, command, timeout=60, check=True):
        return self.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=timeout, check=check)


class GithubReleaseDownloader:
    def __init__(self, log):
        self.log = log

    def ensure_engine(self):
        existing = self.find_exe()
        scripts = self.find_scripts()
        if existing and scripts:
            return existing
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.log("GoodbyeDPI-Turkey release indiriliyor.")
        release = self.fetch_json("https://api.github.com/repos/cagritaskn/GoodbyeDPI-Turkey/releases/latest")
        asset_url = self.pick_zip(release)
        self.download(asset_url, DOWNLOAD_ZIP)
        if ENGINE_DIR.exists():
            shutil.rmtree(ENGINE_DIR)
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(DOWNLOAD_ZIP) as archive:
            archive.extractall(ENGINE_DIR)
        exe = self.find_exe()
        if not exe:
            raise RuntimeError("İndirilen pakette goodbyedpi.exe yok. Release paketi bozuk veya değişmiş.")
        self.log(f"Motor hazır: {exe.parent.name}")
        return exe

    def fetch_json(self, url):
        request = Request(url, headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def pick_zip(self, release):
        assets = release.get("assets", [])
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and "source" not in name:
                return asset["browser_download_url"]
        raise RuntimeError("GoodbyeDPI-Turkey zip asset bulunamadı.")

    def download(self, url, target):
        request = Request(url, headers={"User-Agent": APP_NAME})
        with urlopen(request, timeout=90) as response, target.open("wb") as file:
            shutil.copyfileobj(response, file)

    def find_exe(self):
        candidates = list(ENGINE_DIR.rglob("goodbyedpi.exe"))
        if not candidates:
            return None
        candidates.sort(key=lambda path: ("x86_64" not in str(path).lower(), len(str(path))))
        return candidates[0]

    def find_scripts(self):
        scripts = []
        for pattern in ("*.cmd", "*.bat"):
            scripts.extend(ENGINE_DIR.rglob(pattern))
        return scripts


class EngineInspector:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def help_text(self, exe):
        code, output = self.runner.run([str(exe), "-h"], timeout=10, check=False, cwd=exe.parent)
        if output:
            self.log("Motor -h çıktısı alındı, desteklenen argümanlar doğrulanacak.")
        return output

    def supports(self, help_text, option):
        return option in help_text

    def safe_manual_methods(self, exe):
        help_text = self.help_text(exe)
        base = [["-9"], ["-8"], ["-7"], ["-6"], ["-5"], ["-2"]]
        methods = []
        for index, args in enumerate(base, start=1):
            methods.append(Method(f"Manual preset {args[0]}", "exe", [str(exe), *args], exe.parent, False, 10 - index))
        if self.supports(help_text, "--dns-addr"):
            dns_args = ["--dns-addr", "77.88.8.8", "--dns-port", "1253"]
            if self.supports(help_text, "--dnsv6-addr"):
                dns_args += ["--dnsv6-addr", "2a02:6b8::feed:0ff", "--dnsv6-port", "1253"]
            methods.insert(0, Method("Manual -9 + DNS redir", "exe", [str(exe), "-9", *dns_args], exe.parent, False, 40))
        if self.supports(help_text, "--frag-by-sni"):
            args = ["-f", "2", "-e", "2", "--wrong-seq", "--wrong-chksum", "--reverse-frag", "--frag-by-sni", "--max-payload", "-q"]
            methods.insert(0, Method("Manual SNI fragmentation", "exe", [str(exe), *args], exe.parent, False, 35))
        return methods


class MethodDiscovery:
    def __init__(self, downloader, inspector, log):
        self.downloader = downloader
        self.inspector = inspector
        self.log = log

    def discover(self):
        exe = self.downloader.ensure_engine()
        methods = []
        for script in self.downloader.find_scripts():
            methods.append(self.script_method(script))
        methods.extend(self.inspector.safe_manual_methods(exe))
        methods.sort(key=lambda method: method.score, reverse=True)
        if not methods:
            raise RuntimeError("Çalıştırılacak script veya exe metodu bulunamadı.")
        self.log(f"{len(methods)} çalıştırma metodu bulundu.")
        for method in methods[:8]:
            self.log(f"Metod: {method.name}")
        return methods

    def script_method(self, script):
        name = script.name.lower()
        score = 0
        if "service_install" in name:
            score += 60
        if "dnsredir" in name:
            score += 45
        if "turkey" in name or "türkiye" in name:
            score += 35
        if "alternative" in name or "alternatif" in name:
            score += 10
        if "superonline" in name:
            score += 8
        if "remove" in name or "uninstall" in name:
            score -= 200
        if "service_remove" in name:
            score -= 300
        display = script.stem.replace("_", " ").replace("-", " ")
        command = ["cmd.exe", "/d", "/c", str(script)]
        service_like = "service_install" in name or "install" in name
        return Method(display, "script", command, script.parent, service_like, score)


class WindowsTweaks:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def apply(self):
        self.block_quic()
        self.disable_browser_secure_dns_policy()
        self.disable_chromium_kyber_policy()
        self.flush_network()

    def restore(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.log("QUIC/HTTP3 firewall kuralı kaldırıldı.")

    def block_quic(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.runner.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={QUIC_RULE}", "dir=out", "action=block", "protocol=UDP", "remoteport=443",
        ])
        self.log("QUIC/HTTP3 kapatıldı, trafik TCP'ye zorlandı.")

    def disable_browser_secure_dns_policy(self):
        if winreg is None:
            return
        policies = [
            (r"Software\Policies\Google\Chrome", "DnsOverHttpsMode", "off"),
            (r"Software\Policies\Microsoft\Edge", "DnsOverHttpsMode", "off"),
        ]
        for path, name, value in policies:
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                winreg.CloseKey(key)
            except OSError:
                self.log("Tarayıcı Secure DNS policy yazılamadı.")
        self.log("Chrome/Edge Secure DNS policy kapatıldı.")

    def disable_chromium_kyber_policy(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "PostQuantumKeyAgreementEnabled", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
            except OSError:
                self.log("Chrome/Edge Kyber policy yazılamadı.")
        self.log("Chrome/Edge Kyber policy kapatıldı.")

    def flush_network(self):
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.runner.run(["netsh", "winsock", "reset"], check=False)
        self.log("DNS önbelleği temizlendi, Winsock reset kuyruğa alındı.")


class DnsProfile:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def adapters(self):
        command = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"
        _, output = self.runner.powershell(command)
        names = [line.strip() for line in output.splitlines() if line.strip()]
        if not names:
            raise RuntimeError("Aktif ağ adaptörü bulamadım.")
        return names

    def apply(self):
        names = self.adapters()
        quoted_dns = ",".join(f"'{server}'" for server in DNS_SERVERS)
        for name in names:
            safe_name = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' -ServerAddresses ({quoted_dns})")
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.log(f"DNS ayarlandı: {', '.join(names)}")
        return names

    def restore(self):
        names = self.adapters()
        for name in names:
            safe_name = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe_name}' -ResetServerAddresses", check=False)
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.log(f"DNS otomatiğe döndü: {', '.join(names)}")
        return names


class EngineLauncher:
    def __init__(self, log):
        self.log = log
        self.runner = Runner()
        self.downloader = GithubReleaseDownloader(log)
        self.inspector = EngineInspector(self.runner, log)
        self.discovery = MethodDiscovery(self.downloader, self.inspector, log)
        self.tweaks = WindowsTweaks(self.runner, log)
        self.dns = DnsProfile(self.runner, log)
        self.process = None
        self.methods = []
        self.method_index = 0
        self.active_method = None

    def start(self, index=0):
        self.stop_runtime_only()
        self.dns.apply()
        self.tweaks.apply()
        self.methods = self.discovery.discover()
        self.method_index = min(index, len(self.methods) - 1)
        return self.launch_current()

    def next_method(self):
        if not self.methods:
            self.methods = self.discovery.discover()
        self.method_index = (self.method_index + 1) % len(self.methods)
        self.stop_runtime_only()
        return self.launch_current()

    def launch_current(self):
        method = self.methods[self.method_index]
        self.active_method = method
        self.log(f"Başlatılıyor: {method.name}")
        if method.kind == "script":
            return self.launch_script(method)
        return self.launch_exe(method)

    def launch_script(self, method):
        code, output = self.runner.run(method.command, timeout=25, check=False, cwd=method.cwd)
        self.emit_output(output)
        if code != 0:
            raise RuntimeError(f"Script başarısız: {method.name}\n{output}")
        if method.service_like:
            self.save_state({"method": method.name, "kind": "service_script"})
            self.log("Script başarıyla bitti. Servis tipi kurulum aktif kabul edildi.")
            return method
        self.log("Script başarıyla bitti. Eğer sadece kurulum scriptiyse aktif servis oluşmuş olmalı.")
        return method

    def launch_exe(self, method):
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(
            method.command,
            cwd=str(method.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        time.sleep(2.0)
        if self.process.poll() is not None:
            output = self.read_process_output()
            self.emit_output(output)
            raise RuntimeError(f"GoodbyeDPI hemen kapandı: {method.name}\n{output or 'Çıktı yok. Büyük ihtimalle argüman bu sürümde desteklenmiyor.'}")
        self.save_state({"method": method.name, "kind": "exe", "pid": self.process.pid})
        self.log(f"Motor çalışıyor: {method.name}, pid {self.process.pid}")
        return method

    def stop_runtime_only(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def stop_all(self):
        self.stop_runtime_only()
        self.run_remove_scripts()
        self.kill_leftovers()
        self.tweaks.restore()
        self.dns.restore()
        self.save_state({})

    def run_remove_scripts(self):
        for script in self.downloader.find_scripts():
            name = script.name.lower()
            if "remove" in name or "uninstall" in name or "delete" in name:
                self.log(f"Kaldırma scripti çalışıyor: {script.name}")
                code, output = self.runner.run(["cmd.exe", "/d", "/c", str(script)], timeout=25, check=False, cwd=script.parent)
                self.emit_output(output)
                if code == 0:
                    return

    def kill_leftovers(self):
        self.runner.run(["taskkill", "/IM", "goodbyedpi.exe", "/F"], check=False)
        self.log("Kalan goodbyedpi.exe süreçleri kapatıldı.")

    def read_process_output(self):
        if not self.process or not self.process.stdout:
            return ""
        try:
            return self.process.stdout.read() or ""
        except OSError:
            return ""

    def emit_output(self, output):
        if not output:
            return
        for line in output.splitlines()[-20:]:
            line = line.strip()
            if line:
                self.log(f"motor: {line}")

    def save_state(self, state):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class ConnectivityTester:
    def __init__(self, log):
        self.log = log

    def run(self):
        for host in CHECK_HOSTS:
            self.resolve(host)
        for name, url in CHECK_URLS:
            self.probe(name, url)

    def resolve(self, host):
        try:
            socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            self.log(f"OK  DNS {host}")
        except socket.gaierror as exc:
            self.log(f"FAIL DNS {host}: {exc}")

    def probe(self, name, url):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 SeqDPI"})
            with urlopen(request, timeout=14) as response:
                status = response.status
                ok = status < 500
                self.log(f"{'OK' if ok else 'FAIL'}  {name} HTTP {status}")
        except HTTPError as exc:
            ok = exc.code < 500
            self.log(f"{'OK' if ok else 'FAIL'}  {name} HTTP {exc.code}")
        except URLError as exc:
            self.log(f"FAIL {name}: {exc.reason}")
        except Exception as exc:
            self.log(f"FAIL {name}: {exc}")


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
        self.log_adapter = AppLog(self.append_log)
        self.engine = EngineLauncher(self.log_adapter)
        self.tester = ConnectivityTester(self.log_adapter)
        self.configure_app()
        self.build_ui()
        self.after(250, self.initial_check)

    def configure_app(self):
        self.title(APP_NAME)
        self.geometry("880x660")
        self.minsize(760, 560)
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
        ttk.Label(shell, text="TÜRKİYE GOODBYEDPI SCRIPT LAUNCHER", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Kafadan argüman yok, paketin kendi metodunu çalıştırır", style="Title.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            shell,
            text="Release içindeki gerçek .cmd metodlarını keşfeder, önce Türkiye DNS redir servis scriptini dener, motor kapanırsa çıktıyı gösterir ve tek tuşla sıradaki yönteme geçer.",
            style="Body.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))
        self.main_button = ttk.Button(actions, text="Erişim engelini aç", style="Action.TButton", command=self.enable)
        self.main_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="Sıradaki yöntemi dene", style="Ghost.TButton", command=self.next_method)
        self.next_button.pack(side="left", padx=(12, 0))
        self.test_button = ttk.Button(actions, text="Test et", style="Ghost.TButton", command=self.test)
        self.test_button.pack(side="left", padx=(12, 0))
        self.restore_button = ttk.Button(actions, text="Tamamen kapat", style="Ghost.TButton", command=self.restore)
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
            self.set_status("Bu sürüm Windows için.")
            self.log_adapter("WinDivert ve netsh Windows gerektirir.")
            self.disable_all()
            return
        if not is_admin():
            self.set_status("Yönetici izni gerekiyor.")
            self.log_adapter("DNS, firewall ve WinDivert için yönetici izni şart.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return
        self.set_status("Hazır. Gerçek paket scriptleri kullanılacak.")
        self.log_adapter("Yönetici izni tamam. Kafadan argüman basmayacağım, release içindeki metodlar keşfedilecek.")

    def elevate(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Yönetici olarak açılamadı:\n{exc}")

    def enable(self):
        self.run_background(self.enable_work)

    def enable_work(self):
        try:
            self.set_status("Açılıyor")
            method = self.engine.start(0)
            self.log_adapter(f"Aktif yöntem: {method.name}")
            self.tester.run()
            self.set_status("Aktif. Olmazsa sıradaki yöntemi dene.")
        except Exception as exc:
            self.log_adapter(f"Hata: {exc}")
            self.set_status("Hata verdi, logu oku veya sıradaki yöntemi dene")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def next_method(self):
        self.run_background(self.next_work)

    def next_work(self):
        try:
            self.set_status("Sıradaki yöntem deneniyor")
            method = self.engine.next_method()
            self.log_adapter(f"Aktif yöntem: {method.name}")
            self.tester.run()
            self.set_status("Alternatif aktif.")
        except Exception as exc:
            self.log_adapter(f"Hata: {exc}")
            self.set_status("Alternatif başarısız")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def test(self):
        self.run_background(lambda: self.tester.run())

    def restore(self):
        self.run_background(self.restore_work)

    def restore_work(self):
        try:
            self.set_status("Kapatılıyor")
            self.engine.stop_all()
            self.set_status("Kapandı. Eski ağ profilindesin.")
        except Exception as exc:
            self.log_adapter(f"Kapatma hatası: {exc}")
            self.set_status("Kapatma hatası")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def run_background(self, target):
        self.set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def open_link(self, name):
        import webbrowser
        webbrowser.open(QUICK_LINKS[name])

    def on_close(self):
        if messagebox.askyesno(APP_NAME, "Kapatırken motoru ve servisleri durdurup ayarları geri alayım mı?"):
            try:
                self.engine.stop_all()
            except Exception:
                pass
        self.destroy()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for button in (self.main_button, self.next_button, self.test_button, self.restore_button):
            button.configure(state=state)

    def disable_all(self):
        for button in (self.main_button, self.next_button, self.test_button, self.restore_button):
            button.configure(state="disabled")

    def set_status(self, text):
        self.after(0, lambda: self.status.configure(text=text))

    def append_log(self, message):
        def append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"• {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, append)


if __name__ == "__main__":
    app = SeqDPIApp()
    app.mainloop()
