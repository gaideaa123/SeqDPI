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
DOWNLOAD_ZIP = APP_DIR / "goodbyedpi-0.2.3rc3-turkey.zip"
STATE_FILE = APP_DIR / "state.json"
LOG_FILE = APP_DIR / "seqdpi.log"
TURKEY_MARKER = APP_DIR / "engine-is-turkey-release.json"
TURKEY_RELEASE_API = "https://api.github.com/repos/cagritaskn/GoodbyeDPI-Turkey/releases/latest"
TURKEY_RELEASE_ZIP_HINT = "goodbyedpi-0.2.3rc3-turkey"
QUIC_RULE = "SeqDPI Block QUIC HTTP3"
SERVICE_NAME = "GoodbyeDPI"

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
QUICK_LINKS = {
    "Roblox": "https://www.roblox.com/",
    "Discord": "https://discord.com/app",
}
DNS_SERVERS = ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


@dataclass
class Method:
    name: str
    path: Path
    kind: str
    score: int
    command: list[str]
    keeps_running: bool
    needs_enter: bool = False


class UiLog:
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
    def run(self, args, timeout=60, check=True, cwd=None, input_text=None):
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = CREATE_NO_WINDOW
        completed = subprocess.run(
            args,
            input=input_text,
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
        return self.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            timeout=timeout,
            check=check,
        )


class TurkeyPackage:
    def __init__(self, log):
        self.log = log

    def ensure(self):
        if self.is_valid_turkey_extract():
            self.log("GoodbyeDPI-Turkey paketi hazır.")
            return
        self.log("Eski/yanlış motor temizleniyor. Turkey release zorla indirilecek.")
        if ENGINE_DIR.exists():
            shutil.rmtree(ENGINE_DIR)
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        release = self.fetch_json(TURKEY_RELEASE_API)
        asset = self.pick_asset(release)
        self.download(asset, DOWNLOAD_ZIP)
        with zipfile.ZipFile(DOWNLOAD_ZIP) as archive:
            archive.extractall(ENGINE_DIR)
        if not self.has_turkey_runtime_script():
            raise RuntimeError("Turkey paketinde turkey_dnsredir.cmd bulunamadı. Yanlış asset inmiş olabilir.")
        TURKEY_MARKER.write_text(json.dumps({"asset": asset, "time": time.time()}, indent=2), encoding="utf-8")
        self.log("GoodbyeDPI-Turkey release çıkarıldı. Artık Russia scriptleri kullanılmayacak.")

    def is_valid_turkey_extract(self):
        if not TURKEY_MARKER.exists():
            return False
        return self.has_turkey_runtime_script() and bool(self.goodbyedpi_exe())

    def has_turkey_runtime_script(self):
        return any(path.name.lower() == "turkey_dnsredir.cmd" for path in ENGINE_DIR.rglob("*.cmd"))

    def fetch_json(self, url):
        request = Request(url, headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def pick_asset(self, release):
        assets = release.get("assets", [])
        turkey_assets = []
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and "turkey" in name:
                turkey_assets.append(asset)
        if not turkey_assets:
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".zip") and "source" not in name:
                    turkey_assets.append(asset)
        if not turkey_assets:
            raise RuntimeError("GoodbyeDPI-Turkey release zip asset bulunamadı.")
        return turkey_assets[0]["browser_download_url"]

    def download(self, url, target):
        request = Request(url, headers={"User-Agent": APP_NAME})
        with urlopen(request, timeout=90) as response, target.open("wb") as file:
            shutil.copyfileobj(response, file)

    def scripts(self):
        scripts = []
        for pattern in ("*.cmd", "*.bat"):
            scripts.extend(ENGINE_DIR.rglob(pattern))
        return scripts

    def goodbyedpi_exe(self):
        candidates = list(ENGINE_DIR.rglob("goodbyedpi.exe"))
        if not candidates:
            return None
        candidates.sort(key=lambda path: ("x86_64" not in str(path).lower(), len(str(path))))
        return candidates[0]


class MethodDiscovery:
    def __init__(self, package, log):
        self.package = package
        self.log = log

    def discover(self):
        self.package.ensure()
        methods = []
        for script in self.package.scripts():
            method = self.script_to_method(script)
            if method:
                methods.append(method)
        methods.extend(self.manual_fallbacks())
        methods.sort(key=lambda item: item.score, reverse=True)
        if not methods:
            raise RuntimeError("Turkey paketi içinde çalıştırılacak uygun metod bulunamadı.")
        self.log(f"{len(methods)} Turkey metodu bulundu.")
        for method in methods[:10]:
            self.log(f"Metod: {method.name}")
        return methods

    def script_to_method(self, script):
        lower = script.name.lower()
        if "russia" in lower:
            return None
        if "blacklist" in lower and "turkey" not in lower:
            return None
        if "remove" in lower or "uninstall" in lower or "delete" in lower:
            return None

        stem = script.stem.lower()
        score = 0
        keeps_running = True
        needs_enter = False

        if stem == "turkey_dnsredir":
            score = 1000
        elif re.fullmatch(r"turkey_dnsredir_alternative[1-6]_superonline", stem):
            number = int(re.search(r"alternative([1-6])", stem).group(1))
            score = 900 - number
        elif stem == "service_install_dnsredir_turkey":
            score = 700
            keeps_running = False
            needs_enter = True
        elif re.fullmatch(r"service_install_dnsredir_turkey_alternative[1-6]_superonline", stem):
            number = int(re.search(r"alternative([1-6])", stem).group(1))
            score = 650 - number
            keeps_running = False
            needs_enter = True
        elif "turkey" in stem and "dnsredir" in stem:
            score = 500
        elif stem == "2_any_country_dnsredir":
            score = 120
        else:
            return None

        display = script.stem.replace("_", " ").replace("-", " ")
        return Method(
            name=display,
            path=script,
            kind="script",
            score=score,
            command=["cmd.exe", "/d", "/c", str(script)],
            keeps_running=keeps_running,
            needs_enter=needs_enter,
        )

    def manual_fallbacks(self):
        exe = self.package.goodbyedpi_exe()
        if not exe:
            return []
        fallback_args = [["-9"], ["-8"], ["-7"], ["-6"], ["-5"], ["-2"]]
        methods = []
        for index, args in enumerate(fallback_args):
            methods.append(Method(
                name=f"manual {args[0]}",
                path=exe,
                kind="exe",
                score=80 - index,
                command=[str(exe), *args],
                keeps_running=True,
            ))
        return methods


class WindowsTweaks:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def apply(self):
        self.stop_existing_service()
        self.block_quic()
        self.disable_browser_secure_dns()
        self.disable_chromium_kyber()
        self.flush_dns()

    def restore(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.log("QUIC/HTTP3 firewall kuralı kaldırıldı.")

    def stop_existing_service(self):
        self.runner.run(["sc", "stop", SERVICE_NAME], timeout=15, check=False)
        self.runner.run(["sc", "delete", SERVICE_NAME], timeout=15, check=False)
        self.log("Önceki GoodbyeDPI servisi temizlendi.")

    def block_quic(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"], check=False)
        self.runner.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={QUIC_RULE}", "dir=out", "action=block", "protocol=UDP", "remoteport=443",
        ], check=False)
        self.log("QUIC/HTTP3 kapatıldı, trafik TCP'ye zorlandı.")

    def disable_browser_secure_dns(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "DnsOverHttpsMode", 0, winreg.REG_SZ, "off")
                winreg.CloseKey(key)
            except OSError:
                self.log("Secure DNS policy yazılamadı.")
        self.log("Chrome/Edge Secure DNS policy kapatıldı.")

    def disable_chromium_kyber(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "PostQuantumKeyAgreementEnabled", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
            except OSError:
                self.log("Kyber policy yazılamadı.")
        self.log("Chrome/Edge Kyber policy kapatıldı.")

    def flush_dns(self):
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.log("DNS önbelleği temizlendi.")


class DnsProfile:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def adapters(self):
        _, output = self.runner.powershell(
            "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"
        )
        names = [line.strip() for line in output.splitlines() if line.strip()]
        if not names:
            raise RuntimeError("Aktif ağ adaptörü bulamadım.")
        return names

    def apply(self):
        names = self.adapters()
        quoted = ",".join(f"'{server}'" for server in DNS_SERVERS)
        for name in names:
            safe = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ServerAddresses ({quoted})")
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.log(f"DNS ayarlandı: {', '.join(names)}")

    def restore(self):
        names = self.adapters()
        for name in names:
            safe = name.replace("'", "''")
            self.runner.powershell(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ResetServerAddresses", check=False)
        self.runner.run(["ipconfig", "/flushdns"], check=False)
        self.log(f"DNS otomatiğe döndü: {', '.join(names)}")


class EngineLauncher:
    def __init__(self, log):
        self.log = log
        self.runner = Runner()
        self.package = TurkeyPackage(log)
        self.discovery = MethodDiscovery(self.package, log)
        self.tweaks = WindowsTweaks(self.runner, log)
        self.dns = DnsProfile(self.runner, log)
        self.methods = []
        self.index = 0
        self.process = None
        self.active_method = None

    def start(self):
        self.stop_runtime_only()
        self.dns.apply()
        self.tweaks.apply()
        self.methods = self.discovery.discover()
        self.index = 0
        return self.launch_until_one_sticks()

    def next(self):
        if not self.methods:
            self.methods = self.discovery.discover()
        self.stop_runtime_only()
        self.index = (self.index + 1) % len(self.methods)
        return self.launch_until_one_sticks(start_at_current=True)

    def launch_until_one_sticks(self, start_at_current=False):
        attempts = len(self.methods)
        errors = []
        for _ in range(attempts):
            method = self.methods[self.index]
            try:
                result = self.launch(method)
                self.active_method = method
                self.save_state(method)
                return result
            except Exception as exc:
                errors.append(f"{method.name}: {exc}")
                self.log(f"Metod başarısız: {method.name}. Sıradakine geçiyorum.")
                self.index = (self.index + 1) % len(self.methods)
                if start_at_current:
                    start_at_current = False
        raise RuntimeError("Hiçbir metod çalışmadı:\n" + "\n".join(errors[-6:]))

    def launch(self, method):
        self.log(f"Başlatılıyor: {method.name}")
        if method.kind == "script" and method.needs_enter:
            return self.launch_service_script(method)
        return self.launch_long_running(method)

    def launch_service_script(self, method):
        code, output = self.runner.run(method.command, timeout=35, check=False, cwd=method.path.parent, input_text="\r\n")
        self.log_tail(output)
        if code != 0:
            raise RuntimeError(output or "service script hata koduyla çıktı")
        service_ok = self.service_running()
        if not service_ok:
            raise RuntimeError("service script bitti ama GoodbyeDPI servisi çalışıyor görünmüyor")
        self.log("GoodbyeDPI servisi kuruldu ve çalışıyor.")
        return method

    def launch_long_running(self, method):
        output_file = APP_DIR / f"{safe_filename(method.name)}.runtime.log"
        output_handle = output_file.open("a", encoding="utf-8", errors="replace")
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(
            method.command,
            cwd=str(method.path.parent),
            stdout=output_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        time.sleep(3.0)
        if self.process.poll() is not None:
            output_handle.close()
            output = read_tail(output_file)
            raise RuntimeError(output or "hemen kapandı, çıktı yok")
        self.log(f"Çalışıyor: {method.name}, pid {self.process.pid}")
        return method

    def service_running(self):
        _, output = self.runner.run(["sc", "query", SERVICE_NAME], timeout=12, check=False)
        return "RUNNING" in output.upper()

    def stop_runtime_only(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.runner.run(["taskkill", "/IM", "goodbyedpi.exe", "/F"], check=False)

    def stop_all(self):
        self.stop_runtime_only()
        self.run_remove_script()
        self.tweaks.restore()
        self.dns.restore()
        self.save_empty_state()

    def run_remove_script(self):
        self.package.ensure()
        candidates = [path for path in self.package.scripts() if path.name.lower() == "service_remove.cmd"]
        for script in candidates:
            self.log("service_remove.cmd çalıştırılıyor.")
            code, output = self.runner.run(["cmd.exe", "/d", "/c", str(script)], timeout=35, check=False, cwd=script.parent, input_text="\r\n")
            self.log_tail(output)
            if code == 0:
                break
        self.runner.run(["sc", "stop", SERVICE_NAME], check=False)
        self.runner.run(["sc", "delete", SERVICE_NAME], check=False)

    def log_tail(self, output):
        if not output:
            return
        for line in output.splitlines()[-24:]:
            cleaned = line.strip()
            if cleaned:
                self.log(f"motor: {cleaned}")

    def save_state(self, method):
        STATE_FILE.write_text(json.dumps({"method": method.name, "time": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_empty_state(self):
        STATE_FILE.write_text("{}", encoding="utf-8")


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
                ok = response.status < 500
                self.log(f"{'OK' if ok else 'FAIL'}  {name} HTTP {response.status}")
        except HTTPError as exc:
            ok = exc.code < 500
            self.log(f"{'OK' if ok else 'FAIL'}  {name} HTTP {exc.code}")
        except URLError as exc:
            self.log(f"FAIL {name}: {exc.reason}")
        except Exception as exc:
            self.log(f"FAIL {name}: {exc}")


def read_tail(path, max_chars=5000):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:].strip()
    except OSError:
        return ""


def safe_filename(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "method"


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
        self.logger = UiLog(self.append_log)
        self.engine = EngineLauncher(self.logger)
        self.tester = ConnectivityTester(self.logger)
        self.configure_window()
        self.build_ui()
        self.after(250, self.initial_check)

    def configure_window(self):
        self.title(APP_NAME)
        self.geometry("900x680")
        self.minsize(780, 580)
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
        ttk.Label(shell, text="GOODBYEDPI-TURKEY RUNTIME", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Russia script yok, timeout yok", style="Title.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            shell,
            text="Turkey release zorla indirilir, önce turkey_dnsredir.cmd çalıştırılır. Runtime batch uzun süre açık kalacağı için timeout hatası sayılmaz, servis scriptleri gerekiyorsa Enter otomatik gönderilir.",
            style="Body.TLabel",
            wraplength=780,
        ).pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))
        self.main_button = ttk.Button(actions, text="Erişim engelini aç", style="Action.TButton", command=self.enable)
        self.main_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="Sıradaki Turkey yöntemi", style="Ghost.TButton", command=self.next_method)
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
            self.set_status("Bu sürüm Windows için.")
            self.logger("WinDivert ve netsh Windows gerektirir.")
            self.disable_all()
            return
        if not is_admin():
            self.set_status("Yönetici izni gerekiyor.")
            self.logger("DNS, firewall ve WinDivert için yönetici izni şart.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return
        self.set_status("Hazır. Turkey runtime yöntemi kullanılacak.")
        self.logger("Yönetici izni tamam. Bu sürüm Russia scriptlerini filtreliyor ve Turkey paketini zorla indiriyor.")

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
            method = self.engine.start()
            self.logger(f"Aktif yöntem: {method.name}")
            self.tester.run()
            self.set_status("Aktif. Olmazsa sıradaki Turkey yöntemini dene.")
        except Exception as exc:
            self.logger(f"Hata: {exc}")
            self.set_status("Hata verdi, logu oku")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def next_method(self):
        self.run_background(self.next_work)

    def next_work(self):
        try:
            self.set_status("Sıradaki Turkey yöntemi deneniyor")
            method = self.engine.next()
            self.logger(f"Aktif yöntem: {method.name}")
            self.tester.run()
            self.set_status("Alternatif aktif.")
        except Exception as exc:
            self.logger(f"Hata: {exc}")
            self.set_status("Alternatif başarısız")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def test(self):
        self.run_background(self.tester.run)

    def restore(self):
        self.run_background(self.restore_work)

    def restore_work(self):
        try:
            self.set_status("Kapatılıyor")
            self.engine.stop_all()
            self.set_status("Kapandı. Eski ağ profilindesin.")
        except Exception as exc:
            self.logger(f"Kapatma hatası: {exc}")
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
        if messagebox.askyesno(APP_NAME, "Kapatırken motoru/servisi durdurup DNS ve firewall ayarlarını geri alayım mı?"):
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
