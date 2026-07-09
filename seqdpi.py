import ctypes
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "SeqDPI"
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
ENGINE_DIR = APP_DIR / "engine-turkey-current"
LEGACY_ENGINE_DIR = APP_DIR / "engine"
DOWNLOAD_ZIP = APP_DIR / "goodbyedpi-0.2.3rc3-turkey.zip"
LOG_FILE = APP_DIR / "seqdpi.log"
STATE_FILE = APP_DIR / "state.json"
TURKEY_MARKER = ENGINE_DIR / "engine-is-turkey-release.json"
DISCORD_LIST = APP_DIR / "discord-hosts.txt"
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
DISCORD_HOSTS = [
    "discord.com", "gateway.discord.gg", "cdn.discordapp.com", "media.discordapp.net",
    "images-ext-1.discordapp.net", "discordapp.com", "discordapp.net", "discord.gg",
    "updates.discord.com", "dl.discordapp.net", "discordstatus.com", "dis.gd",
]
ROBLOX_HOSTS = ["roblox.com", "www.roblox.com", "auth.roblox.com", "games.roblox.com"]
CHECK_HOSTS = ["wikipedia.org", *DISCORD_HOSTS[:10], *ROBLOX_HOSTS]
CHECK_URLS = [
    ("Discord web", "https://discord.com/"),
    ("Discord gateway", "https://gateway.discord.gg/"),
    ("Discord update", "https://updates.discord.com/distributions/app/manifests/latest?channel=stable&platform=win&arch=x64"),
    ("Discord CDN", "https://cdn.discordapp.com/"),
    ("Roblox", "https://www.roblox.com/"),
    ("Wikipedia", "https://www.wikipedia.org/"),
]
QUICK_LINKS = {"Roblox": "https://www.roblox.com/", "Discord": "https://discord.com/app"}

@dataclass
class Method:
    name: str
    path: Path
    command: list[str]
    score: int
    service: bool = False
    dns_redir: bool = False

class UiLog:
    def __init__(self, callback):
        self.callback = callback
        APP_DIR.mkdir(parents=True, exist_ok=True)

    def __call__(self, message):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(f"[{stamp}] {message}\n")
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
        completed = subprocess.run(
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
        output = (completed.stdout + completed.stderr).strip()
        if check and completed.returncode != 0:
            raise RuntimeError(output or f"Komut başarısız: {args[0]}")
        return completed.returncode, output

    def ps(self, command, timeout=60, check=False):
        return self.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=timeout, check=check)

class ProcessCleaner:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def before_launch(self):
        self.stop_service()
        self.kill_engine_processes()
        self.kill_goodbyedpi()
        self.stop_windivert()

    def stop_service(self):
        self.runner.run(["sc", "stop", SERVICE_NAME], timeout=12)
        self.runner.run(["sc", "delete", SERVICE_NAME], timeout=12)
        self.log("GoodbyeDPI servisi temizlendi.")

    def kill_goodbyedpi(self):
        self.runner.run(["taskkill", "/IM", "goodbyedpi.exe", "/F", "/T"], timeout=12)
        self.log("goodbyedpi.exe süreçleri kapatıldı.")

    def kill_engine_processes(self):
        needle = str(APP_DIR).replace("'", "''")
        pid = os.getpid()
        command = (
            f"$needle='{needle}'; "
            f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne {pid} -and $_.CommandLine -and $_.CommandLine.Contains($needle) }} | "
            "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"
        )
        self.runner.ps(command, timeout=20)
        self.log("SeqDPI engine klasörünü tutan eski süreçler kapatıldı.")

    def stop_windivert(self):
        for name in ("WinDivert", "WinDivert1.4", "WinDivert2.2", "windivert", "windivert14"):
            self.runner.run(["sc", "stop", name], timeout=5)
        self.log("WinDivert kilitleri best-effort durduruldu.")

class DnsManager:
    def __init__(self, runner, log):
        self.runner = runner
        self.log = log

    def adapters(self):
        _, out = self.runner.ps("Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name")
        names = [line.strip() for line in out.splitlines() if line.strip()]
        return names

    def set_servers(self, label, servers):
        names = self.adapters()
        if not names:
            self.log("Aktif ağ adaptörü bulunamadı, DNS ayarı atlandı.")
            return False
        quoted = ",".join(f"'{server}'" for server in servers)
        ok = False
        for name in names:
            safe = name.replace("'", "''")
            code, out = self.runner.ps(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ServerAddresses ({quoted})")
            ok = ok or code == 0
        self.flush()
        self.log(f"DNS {label} olarak ayarlandı: {', '.join(names)}")
        return ok

    def restore(self):
        for name in self.adapters():
            safe = name.replace("'", "''")
            self.runner.ps(f"Set-DnsClientServerAddress -InterfaceAlias '{safe}' -ResetServerAddresses")
        self.flush()
        self.log("DNS otomatiğe döndü.")

    def flush(self):
        self.runner.run(["ipconfig", "/flushdns"], timeout=15)

    def dns_is_ok(self):
        return dns_resolves("discord.com") or dns_resolves("roblox.com") or dns_resolves("wikipedia.org")

    def establish_working_dns(self):
        # Critical change: DNS preflight is advisory. Some networks block every public resolver,
        # but a DPI method can still be useful. Never stop startup here.
        if self.dns_is_ok():
            self.log("Mevcut DNS zaten çalışıyor, değiştirmeden devam.")
            return "current"
        errors = []
        for label, servers in DNS_PROFILES:
            try:
                self.set_servers(label, servers)
                if self.dns_is_ok():
                    self.log(f"DNS sağlık kontrolü OK: {label}")
                    return label
                errors.append(f"{label}: çözümleme yok")
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        try:
            self.restore()
            if self.dns_is_ok():
                self.log("DNS otomatik profil ile çalıştı.")
                return "automatic"
        except Exception as exc:
            errors.append(f"automatic: {exc}")
        self.log("Uyarı: hiçbir DNS profili doğrulanamadı, ama motor yine denenecek.")
        self.log("DNS deneme özeti: " + " | ".join(errors[-4:]))
        return "unverified"

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
        self.cleanup_legacy()
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
        try:
            trash = APP_DIR / f"trash-{path.name}-{int(time.time())}"
            path.rename(trash)
            shutil.rmtree(trash, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
        except OSError:
            self.delete_on_reboot(path)

    def cleanup_legacy(self):
        if LEGACY_ENGINE_DIR.exists():
            self.safe_remove(LEGACY_ENGINE_DIR)

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
        self.write_discord_list()
        methods = self.discord_safe_methods() + self.script_methods()
        methods.sort(key=lambda m: m.score, reverse=True)
        self.log(f"{len(methods)} metod bulundu.")
        for method in methods[:14]:
            tag = "dnsredir" if method.dns_redir else "safe"
            self.log(f"Metod: {method.name} ({tag})")
        return methods

    def write_discord_list(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        hosts = [*DISCORD_HOSTS, *ROBLOX_HOSTS]
        DISCORD_LIST.write_text("\n".join(dict.fromkeys(hosts)) + "\n", encoding="utf-8")

    def discord_safe_methods(self):
        exe = self.package.exe()
        if not exe:
            return []
        presets = ["-2", "-1", "-4", "-6", "-5", "-7", "-8", "-9"]
        methods = []
        for i, p in enumerate(presets):
            methods.append(Method(f"discord safe {p}", exe, [str(exe), p, "--blacklist", str(DISCORD_LIST)], 4000 - i))
            methods.append(Method(f"manual {p}", exe, [str(exe), p], 2500 - i))
        return methods

    def script_methods(self):
        methods = []
        for script in self.package.scripts():
            lower = script.name.lower()
            if "russia" in lower or "blacklist" in lower or "remove" in lower or "uninstall" in lower:
                continue
            stem = script.stem.lower()
            if "turkey" not in stem and "any_country" not in stem:
                continue
            content = read_text(script).lower()
            dns_redir = "--dns-addr" in content or "--dns-port" in content
            service = "service_install" in stem
            score = -200 if dns_redir else 1000
            if "alternative4" in stem:
                score += 450
            if "alternative2" in stem:
                score += 350
            if "superonline" in stem:
                score += 120
            if service:
                score -= 120
            methods.append(Method(script.stem.replace("_", " "), script, ["cmd.exe", "/d", "/c", str(script)], score, service=service, dns_redir=dns_redir))
        return methods

class Health:
    def __init__(self, log):
        self.log = log

    def dns_ok(self):
        ok = sum(1 for host in ("discord.com", "roblox.com", "wikipedia.org") if dns_resolves(host))
        self.log(f"DNS sağlık skoru: {ok}/3")
        return ok >= 1

    def discord_ok(self):
        if not dns_resolves("discord.com"):
            self.log("Discord sağlık: DNS yok")
            return False
        probes = CHECK_URLS[:4]
        ok_count = 0
        for name, url in probes:
            ok, detail = http_probe(url)
            self.log(f"{'OK' if ok else 'FAIL'} {name} ({detail})")
            if ok:
                ok_count += 1
        self.log(f"Discord sağlık skoru: {ok_count}/{len(probes)}")
        return ok_count >= 1

    def full_report(self):
        for host in CHECK_HOSTS:
            self.log(f"{'OK' if dns_resolves(host) else 'FAIL'} DNS {host}")
        for name, url in CHECK_URLS:
            ok, detail = http_probe(url)
            self.log(f"{'OK' if ok else 'FAIL'} {name} ({detail})")

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
        self.last_method = None

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
                self.last_method = method
                if self.health.dns_ok() and self.health.discord_ok():
                    self.log(f"Aktif yöntem sağlıklı: {method.name}")
                    STATE_FILE.write_text(json.dumps({"method": method.name, "time": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
                    return method
                raise RuntimeError("sağlık kontrolü geçmedi")
            except Exception as exc:
                errors.append(f"{method.name}: {exc}")
                self.log(f"Metod başarısız/reddedildi: {method.name}: {exc}")
                self.stop_runtime_only()
                self.dns.establish_working_dns()
                self.index = (self.index + 1) % len(self.methods)
        if self.last_method:
            self.log("Uyarı: sağlık testleri geçmedi, son çalışan motor açık bırakıldı.")
            return self.last_method
        raise RuntimeError("Çalışan metod bulunamadı:\n" + "\n".join(errors[-8:]))

    def launch(self, method):
        self.log(f"Başlatılıyor: {method.name}")
        if method.service:
            code, out = self.runner.run(method.command, timeout=40, cwd=method.path.parent, input_text="\r\n")
            log_tail(out, self.log)
            if code != 0:
                raise RuntimeError(out or "service script hata koduyla çıktı")
        else:
            self.launch_process(method)
        time.sleep(1.0)

    def launch_process(self, method):
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
        socket.getaddrinfo(host, 443, family=socket.AF_INET, proto=socket.IPPROTO_TCP)
        return True
    except socket.gaierror:
        return False

def http_probe(url):
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        try:
            p = subprocess.run([curl, "-L", "--http1.1", "--connect-timeout", "8", "--max-time", "12", "-o", "NUL", "-s", "-w", "%{http_code}", url], capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
            code = (p.stdout or "").strip()[-3:]
            if code.isdigit() and int(code) < 500:
                return True, f"curl HTTP {code}"
        except Exception:
            pass
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 SeqDPI"})
        context = ssl.create_default_context()
        context.options |= getattr(ssl, "OP_NO_TICKET", 0)
        with urlopen(req, timeout=12, context=context) as res:
            return res.status < 500, f"HTTP {res.status}"
    except HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except (URLError, ssl.SSLError) as exc:
        detail = str(getattr(exc, "reason", exc))
        if "INVALID_SESSION_ID" in detail:
            return True, "TLS reached server, Python probe hit INVALID_SESSION_ID"
        return False, detail
    except Exception as exc:
        detail = str(exc)
        if "INVALID_SESSION_ID" in detail:
            return True, "TLS reached server, Python probe hit INVALID_SESSION_ID"
        return False, detail

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
