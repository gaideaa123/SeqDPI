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
LEGACY_ENGINE_DIR = APP_DIR / "engine"
ENGINE_DIR = APP_DIR / "engine-turkey-current"
DOWNLOAD_ZIP = APP_DIR / "goodbyedpi-0.2.3rc3-turkey.zip"
LOG_FILE = APP_DIR / "seqdpi.log"
STATE_FILE = APP_DIR / "state.json"
TURKEY_MARKER = ENGINE_DIR / "engine-is-turkey-release.json"
TURKEY_RELEASE_API = "https://api.github.com/repos/cagritaskn/GoodbyeDPI-Turkey/releases/latest"
SERVICE_NAME = "GoodbyeDPI"
QUIC_RULE = "SeqDPI Block QUIC HTTP3"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004

DNS_PROFILES = [
    ("Cloudflare", ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]),
    ("Google", ["8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"]),
    ("Yandex", ["77.88.8.8", "77.88.8.1", "2a02:6b8::feed:0ff", "2a02:6b8:0:1::feed:0ff"]),
]
CHECK_HOSTS = ["wikipedia.org", "discord.com", "gateway.discord.gg", "roblox.com", "www.roblox.com", "auth.roblox.com", "games.roblox.com"]
CHECK_URLS = [("Roblox", "https://www.roblox.com/"), ("Discord", "https://discord.com/"), ("Wikipedia", "https://www.wikipedia.org/")]
QUICK_LINKS = {"Roblox": "https://www.roblox.com/", "Discord": "https://discord.com/app"}


@dataclass
class Method:
    name: str
    path: Path
    kind: str
    command: list[str]
    score: int
    needs_enter: bool = False
    dns_redir: bool = False
    service: bool = False


class UiLog:
    def __init__(self, callback):
        self.callback = callback
        APP_DIR.mkdir(parents=True, exist_ok=True)

    def __call__(self, message):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(f"[{stamp}] {message}\n")
        except OSError:
            pass
        self.callback(message)


class Runner:
    def run(self, args, timeout=60, check=False, cwd=None, input_text=None):
        startupinfo = None
        flags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            flags = CREATE_NO_WINDOW
        p = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=flags,
            cwd=str(cwd) if cwd else None,
        )
        out = (p.stdout + p.stderr).strip()
        if check and p.returncode != 0:
            raise RuntimeError(out or f"Komut başarısız: {args[0]}")
        return p.returncode, out

    def ps(self, command, timeout=60, check=False):
        return self.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=timeout, check=check)


class ProcessCleaner:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def before_launch(self):
        self.stop_service()
        self.kill_seqdpi_engine_processes()
        self.kill_goodbyedpi()
        self.stop_windivert_best_effort()

    def stop_service(self):
        self.runner.run(["sc", "stop", SERVICE_NAME], timeout=12)
        self.runner.run(["sc", "delete", SERVICE_NAME], timeout=12)
        self.log("GoodbyeDPI servisi temizlendi.")

    def kill_goodbyedpi(self):
        self.runner.run(["taskkill", "/IM", "goodbyedpi.exe", "/F", "/T"], timeout=12)
        self.log("goodbyedpi.exe süreçleri kapatıldı.")

    def kill_seqdpi_engine_processes(self):
        needle = str(APP_DIR).replace("'", "''")
        pid = os.getpid()
        cmd = (
            f"$needle = '{needle}'; "
            f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne {pid} -and $_.CommandLine -and $_.CommandLine.Contains($needle) }} | "
            "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"
        )
        self.runner.ps(cmd, timeout=20)
        self.log("SeqDPI engine klasörünü tutan eski süreçler kapatıldı.")

    def stop_windivert_best_effort(self):
        for name in ("WinDivert", "WinDivert1.4", "WinDivert2.2", "windivert", "windivert14"):
            self.runner.run(["sc", "stop", name], timeout=5)
        self.log("WinDivert kilitleri best-effort durduruldu.")


class DnsManager:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def adapters(self):
        _, out = self.runner.ps("Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name", check=True)
        names = [x.strip() for x in out.splitlines() if x.strip()]
        if not names:
            raise RuntimeError("Aktif ağ adaptörü bulamadım.")
        return names

    def set_servers(self, label, servers):
        names = self.adapters()
        quoted = ",".join(f"'{s}'" for s in servers)
        for name in names:
            safe = name.replace("'", "''")
            self.runner.ps(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ServerAddresses ({quoted})", check=True)
        self.flush()
        self.log(f"DNS {label} olarak ayarlandı: {', '.join(names)}")
        return names

    def restore(self):
        for name in self.adapters():
            safe = name.replace("'", "''")
            self.runner.ps(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ResetServerAddresses")
        self.flush()
        self.log("DNS otomatiğe döndü.")

    def flush(self):
        self.runner.run(["ipconfig", "/flushdns"], timeout=15)

    def establish_working_dns(self):
        errors = []
        for label, servers in DNS_PROFILES:
            try:
                self.set_servers(label, servers)
                if dns_resolves("wikipedia.org") or dns_resolves("discord.com"):
                    self.log(f"DNS sağlık kontrolü OK: {label}")
                    return label
                errors.append(f"{label}: çözümleme yok")
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        raise RuntimeError("Hiçbir DNS profili çalışmadı: " + " | ".join(errors))


class WindowsTweaks:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def apply(self):
        self.block_quic()
        self.disable_secure_dns()
        self.disable_kyber()

    def block_quic(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"])
        self.runner.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={QUIC_RULE}", "dir=out", "action=block", "protocol=UDP", "remoteport=443"])
        self.log("QUIC/HTTP3 kapatıldı, TCP zorlandı.")

    def restore(self):
        self.runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={QUIC_RULE}"])
        self.log("QUIC/HTTP3 firewall kuralı kaldırıldı.")

    def disable_secure_dns(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "DnsOverHttpsMode", 0, winreg.REG_SZ, "off")
                winreg.CloseKey(key)
            except OSError:
                pass
        self.log("Chrome/Edge Secure DNS policy kapatıldı.")

    def disable_kyber(self):
        if winreg is None:
            return
        for path in (r"Software\Policies\Google\Chrome", r"Software\Policies\Microsoft\Edge"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "PostQuantumKeyAgreementEnabled", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
            except OSError:
                pass
        self.log("Chrome/Edge Kyber policy kapatıldı.")


class TurkeyPackage:
    def __init__(self, runner, cleaner, log):
        self.runner = runner
        self.cleaner = cleaner
        self.log = log

    def ensure(self):
        self.cleanup_legacy_best_effort()
        if self.valid():
            self.log("GoodbyeDPI-Turkey paketi hazır.")
            return
        self.cleaner.before_launch()
        self.replace()

    def valid(self):
        return TURKEY_MARKER.exists() and self.has_script("turkey_dnsredir.cmd") and self.exe() is not None

    def replace(self):
        self.log("Turkey release indiriliyor.")
        self.safe_remove(ENGINE_DIR)
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        release = self.fetch_json(TURKEY_RELEASE_API)
        asset = self.pick_asset(release)
        self.download(asset, DOWNLOAD_ZIP)
        with zipfile.ZipFile(DOWNLOAD_ZIP) as z:
            z.extractall(ENGINE_DIR)
        if not self.has_script("turkey_dnsredir.cmd"):
            raise RuntimeError("Turkey paketinde turkey_dnsredir.cmd yok. Yanlış paket indi.")
        TURKEY_MARKER.write_text(json.dumps({"asset": asset, "time": time.time()}, indent=2), encoding="utf-8")
        self.log("GoodbyeDPI-Turkey release çıkarıldı.")

    def fetch_json(self, url):
        req = Request(url, headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def pick_asset(self, release):
        for asset in release.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and "turkey" in name:
                return asset["browser_download_url"]
        raise RuntimeError("GoodbyeDPI-Turkey zip asset bulunamadı.")

    def download(self, url, target):
        req = Request(url, headers={"User-Agent": APP_NAME})
        with urlopen(req, timeout=90) as r, target.open("wb") as f:
            shutil.copyfileobj(r, f)

    def scripts(self):
        out = []
        for pattern in ("*.cmd", "*.bat"):
            out.extend(ENGINE_DIR.rglob(pattern))
        return out

    def has_script(self, name):
        return any(p.name.lower() == name.lower() for p in self.scripts())

    def exe(self):
        candidates = list(ENGINE_DIR.rglob("goodbyedpi.exe"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: ("x86_64" not in str(p).lower(), len(str(p))))
        return candidates[0]

    def safe_remove(self, path):
        if not path.exists():
            return
        trash = APP_DIR / f"trash-{path.name}-{int(time.time())}"
        try:
            path.rename(trash)
            shutil.rmtree(trash, onerror=self.remove_error)
        except OSError as exc:
            self.log(f"Kilitli klasör silinemedi, reboot'a bırakıldı: {path.name} ({exc})")
            self.delete_on_reboot(path)

    def cleanup_legacy_best_effort(self):
        if LEGACY_ENGINE_DIR.exists():
            self.safe_remove(LEGACY_ENGINE_DIR)

    def remove_error(self, func, path, _):
        os.chmod(path, 0o700)
        func(path)

    def delete_on_reboot(self, path):
        if os.name == "nt":
            try:
                ctypes.windll.kernel32.MoveFileExW(str(path), None, MOVEFILE_DELAY_UNTIL_REBOOT)
            except Exception:
                pass


class MethodDiscovery:
    def __init__(self, package, log):
        self.package = package
        self.log = log

    def discover(self):
        self.package.ensure()
        methods = self.manual_methods() + self.script_methods()
        methods.sort(key=lambda m: m.score, reverse=True)
        if not methods:
            raise RuntimeError("Çalıştırılacak metod bulunamadı.")
        self.log(f"{len(methods)} metod bulundu.")
        for method in methods[:12]:
            tag = "dnsredir" if method.dns_redir else "dns-safe"
            self.log(f"Metod: {method.name} ({tag})")
        return methods

    def manual_methods(self):
        exe = self.package.exe()
        if not exe:
            return []
        # Manual no-dnsredir modes are first now. The user's log proves dnsredir can kill all DNS.
        presets = ["-9", "-8", "-7", "-6", "-5", "-2", "-1"]
        return [Method(f"manual {p} no dnsredir", exe, "exe", [str(exe), p], 2000 - i, dns_redir=False) for i, p in enumerate(presets)]

    def script_methods(self):
        methods = []
        for script in self.package.scripts():
            m = self.script_to_method(script)
            if m:
                methods.append(m)
        return methods

    def script_to_method(self, script):
        lower = script.name.lower()
        if "russia" in lower or "blacklist" in lower or "remove" in lower or "uninstall" in lower:
            return None
        stem = script.stem.lower()
        if "turkey" not in stem and "any_country" not in stem:
            return None
        content = read_text(script).lower()
        dns_redir = "--dns-addr" in content or "--dns-port" in content
        service = "service_install" in stem
        needs_enter = service or "pause" in content
        score = 0
        if not dns_redir:
            score += 1000
        else:
            score -= 400
        if "alternative2" in stem or "alternative4" in stem:
            score += 300
        if "superonline" in stem:
            score += 100
        if stem == "turkey_dnsredir":
            score += 150
        if service:
            score -= 100
        return Method(script.stem.replace("_", " "), script, "script", ["cmd.exe", "/d", "/c", str(script)], score, needs_enter, dns_redir, service)


class Health:
    def __init__(self, log):
        self.log = log

    def dns_ok(self):
        ok = 0
        for host in ("wikipedia.org", "discord.com", "roblox.com"):
            if dns_resolves(host):
                ok += 1
        self.log(f"DNS sağlık skoru: {ok}/3")
        return ok >= 1

    def full_report(self):
        for host in CHECK_HOSTS:
            if dns_resolves(host):
                self.log(f"OK  DNS {host}")
            else:
                self.log(f"FAIL DNS {host}")
        for name, url in CHECK_URLS:
            ok, detail = http_probe(url)
            self.log(f"{'OK' if ok else 'FAIL'}  {name} ({detail})")


class EngineLauncher:
    def __init__(self, log):
        self.log = log
        self.runner = Runner()
        self.cleaner = ProcessCleaner(self.runner, log)
        self.dns = DnsManager(self.runner, log)
        self.tweaks = WindowsTweaks(self.runner, log)
        self.package = TurkeyPackage(self.runner, self.cleaner, log)
        self.discovery = MethodDiscovery(self.package, log)
        self.health = Health(log)
        self.methods = []
        self.index = 0
        self.process = None

    def start(self):
        self.stop_runtime_only()
        self.cleaner.before_launch()
        self.dns.establish_working_dns()
        self.tweaks.apply()
        self.methods = self.discovery.discover()
        self.index = 0
        return self.launch_until_healthy()

    def next(self):
        if not self.methods:
            self.methods = self.discovery.discover()
        self.stop_runtime_only()
        self.index = (self.index + 1) % len(self.methods)
        return self.launch_until_healthy()

    def launch_until_healthy(self):
        errors = []
        for _ in range(len(self.methods)):
            method = self.methods[self.index]
            try:
                self.launch(method)
                if self.health.dns_ok():
                    self.log(f"Aktif yöntem sağlıklı: {method.name}")
                    STATE_FILE.write_text(json.dumps({"method": method.name, "time": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
                    return method
                raise RuntimeError("DNS öldü, bu metod reddedildi")
            except Exception as exc:
                errors.append(f"{method.name}: {exc}")
                self.log(f"Metod başarısız/reddedildi: {method.name}: {exc}")
                self.stop_runtime_only()
                self.dns.establish_working_dns()
                self.index = (self.index + 1) % len(self.methods)
        raise RuntimeError("Sağlıklı metod bulunamadı:\n" + "\n".join(errors[-8:]))

    def launch(self, method):
        self.log(f"Başlatılıyor: {method.name}")
        if method.kind == "script" and method.service:
            self.launch_service_script(method)
        else:
            self.launch_long_running(method)
        time.sleep(1.0)

    def launch_service_script(self, method):
        code, out = self.runner.run(method.command, timeout=40, cwd=method.path.parent, input_text="\r\n")
        log_tail(out, self.log)
        if code != 0:
            raise RuntimeError(out or "service script hata koduyla çıktı")
        if not self.service_running():
            raise RuntimeError("servis çalışıyor görünmüyor")
        self.log("GoodbyeDPI servisi çalışıyor.")

    def launch_long_running(self, method):
        log_file = APP_DIR / f"{safe_filename(method.name)}.runtime.log"
        handle = log_file.open("a", encoding="utf-8", errors="replace")
        startupinfo = None
        flags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(method.command, cwd=str(method.path.parent), stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo, creationflags=flags)
        time.sleep(3.0)
        if self.process.poll() is not None:
            handle.close()
            raise RuntimeError(read_tail(log_file) or "hemen kapandı, çıktı yok")
        self.log(f"Çalışıyor: {method.name}, pid {self.process.pid}")

    def service_running(self):
        _, out = self.runner.run(["sc", "query", SERVICE_NAME], timeout=12)
        return "RUNNING" in out.upper()

    def stop_runtime_only(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.cleaner.stop_service()
        self.cleaner.kill_goodbyedpi()

    def stop_all(self):
        self.stop_runtime_only()
        self.tweaks.restore()
        self.dns.restore()
        STATE_FILE.write_text("{}", encoding="utf-8")


def dns_resolves(host):
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True
    except socket.gaierror:
        return False


def http_probe(url):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 SeqDPI"})
        with urlopen(req, timeout=12) as res:
            return res.status < 500, f"HTTP {res.status}"
    except HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:
        return False, str(exc)


def read_text(path):
    for enc in ("utf-8", "cp1254", "cp866", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except OSError:
            return ""
    return ""


def read_tail(path, max_chars=5000):
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-max_chars:].strip()
    except OSError:
        return ""


def log_tail(text, log):
    if not text:
        return
    for line in text.splitlines()[-24:]:
        if line.strip():
            log(f"motor: {line.strip()}")


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
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


class SeqDPIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.logger = UiLog(self.append_log)
        self.engine = EngineLauncher(self.logger)
        self.health = Health(self.logger)
        self.configure_window()
        self.build_ui()
        self.after(250, self.initial_check)

    def configure_window(self):
        self.title(APP_NAME)
        self.geometry("900x680")
        self.minsize(780, 580)
        self.configure(bg="#f7f5ef")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
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
        ttk.Label(shell, text="DNS HEALTH-GATED DPI", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(shell, text="DNS’i öldüren metod otomatik elenir", style="Title.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(shell, text="Önce sağlam DNS kurar, DNS redirection yerine no-dnsredir manuel modları dener, her metodu DNS sağlık kontrolünden geçirir. DNS ölürse metodu kapatıp sıradakine geçer.", style="Body.TLabel", wraplength=780).pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))
        self.main_button = ttk.Button(actions, text="Erişim engelini aç", style="Action.TButton", command=self.enable)
        self.main_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="Sıradaki yöntem", style="Ghost.TButton", command=self.next_method)
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
        frame = tk.Frame(shell, bg="#2b261f")
        frame.pack(fill="both", expand=True)
        self.log_box = tk.Text(frame, bg="#2b261f", fg="#f3ede3", insertbackground="#f3ede3", relief="flat", padx=18, pady=16, font=("Cascadia Mono", 10), wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def initial_check(self):
        if not is_windows():
            self.set_status("Bu sürüm Windows için.")
            self.disable_all()
            return
        if not is_admin():
            self.set_status("Yönetici izni gerekiyor.")
            self.logger("DNS, firewall ve WinDivert için yönetici izni şart.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return
        self.set_status("Hazır. DNS sağlık kontrollü mod kullanılacak.")
        self.logger("Yönetici izni tamam. DNS’i öldüren dnsredir metodları artık başarı sayılmayacak.")

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
            self.health.full_report()
            self.set_status("Aktif. DNS sağlıklı.")
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
            self.set_status("Sıradaki yöntem deneniyor")
            method = self.engine.next()
            self.logger(f"Aktif yöntem: {method.name}")
            self.health.full_report()
            self.set_status("Alternatif aktif.")
        except Exception as exc:
            self.logger(f"Hata: {exc}")
            self.set_status("Alternatif başarısız")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            self.set_busy(False)

    def test(self):
        self.run_background(self.health.full_report)

    def restore(self):
        self.run_background(self.restore_work)

    def restore_work(self):
        try:
            self.set_status("Kapatılıyor")
            self.engine.stop_all()
            self.set_status("Kapandı. Eski ağ profilindesin.")
        except Exception as exc:
            self.logger(f"Kapatma hatası: {exc}")
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
        if messagebox.askyesno(APP_NAME, "Kapatırken motoru durdurup DNS/firewall ayarlarını geri alayım mı?"):
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
    SeqDPIApp().mainloop()
