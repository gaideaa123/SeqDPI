import ctypes
import json
import os
import select
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "SeqDPI"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 18991
DNS_SERVERS = [
    "1.1.1.1",
    "1.0.0.1",
    "2606:4700:4700::1111",
    "2606:4700:4700::1001",
]
CHECK_HOSTS = [
    "roblox.com",
    "auth.roblox.com",
    "games.roblox.com",
    "discord.com",
    "gateway.discord.gg",
]
QUICK_LINKS = {
    "Roblox": "https://www.roblox.com/",
    "Discord": "https://discord.com/app",
}
BACKUP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
BACKUP_FILE = BACKUP_DIR / "network-backup.json"


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


class WindowsProxyProfile:
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    def __init__(self):
        self.runner = Runner()

    def read_current(self):
        if winreg is None:
            return {}
        data = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_READ) as key:
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
                try:
                    value, reg_type = winreg.QueryValueEx(key, name)
                    data[name] = {"value": value, "type": reg_type}
                except FileNotFoundError:
                    data[name] = None
        return data

    def save_backup(self):
        if BACKUP_FILE.exists():
            return
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_FILE.write_text(json.dumps(self.read_current(), ensure_ascii=False, indent=2), encoding="utf-8")

    def set_value(self, key, name, payload):
        if payload is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
            return
        winreg.SetValueEx(key, name, 0, payload["type"], payload["value"])

    def enable(self):
        if winreg is None:
            raise RuntimeError("Windows kayıt defteri erişimi yok.")
        self.save_backup()
        proxy = f"http={PROXY_HOST}:{PROXY_PORT};https={PROXY_HOST}:{PROXY_PORT}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
        self.refresh()
        self.runner.run(["netsh", "winhttp", "set", "proxy", f"{PROXY_HOST}:{PROXY_PORT}"])

    def restore(self):
        if winreg is not None and BACKUP_FILE.exists():
            data = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
                    self.set_value(key, name, data.get(name))
            BACKUP_FILE.unlink(missing_ok=True)
        elif winreg is not None:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        self.refresh()
        self.runner.run(["netsh", "winhttp", "reset", "proxy"])

    def refresh(self):
        if os.name != "nt":
            return
        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        ctypes.windll.Wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        ctypes.windll.Wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)


class FragmentingProxy:
    def __init__(self, host=PROXY_HOST, port=PROXY_PORT):
        self.host = host
        self.port = port
        self.server = None
        self.running = threading.Event()
        self.threads = []

    def start(self):
        if self.running.is_set():
            return
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(80)
        self.running.set()
        thread = threading.Thread(target=self.accept_loop, daemon=True)
        thread.start()
        self.threads.append(thread)

    def stop(self):
        self.running.clear()
        if self.server:
            try:
                self.server.close()
            except OSError:
                pass
            self.server = None

    def accept_loop(self):
        while self.running.is_set():
            try:
                client, _ = self.server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client,), daemon=True)
                thread.start()
                self.threads.append(thread)
            except OSError:
                break

    def handle_client(self, client):
        upstream = None
        try:
            client.settimeout(10)
            first = client.recv(65535)
            if not first:
                return
            method, target = self.parse_first_line(first)
            if method == "CONNECT":
                host, port = self.parse_connect_target(target)
                upstream = socket.create_connection((host, port), timeout=12)
                client.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: SeqDPI\r\n\r\n")
                self.tunnel(client, upstream, fragment_client=True)
            else:
                host, port = self.parse_http_target(first)
                upstream = socket.create_connection((host, port), timeout=12)
                self.send_fragmented(upstream, first)
                self.tunnel(client, upstream, fragment_client=False)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
        finally:
            for sock in (client, upstream):
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass

    def parse_first_line(self, data):
        line = data.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = line.split()
        if len(parts) < 2:
            raise ValueError("Geçersiz proxy isteği")
        return parts[0].upper(), parts[1]

    def parse_connect_target(self, target):
        if ":" in target:
            host, port = target.rsplit(":", 1)
            return host.strip("[]"), int(port)
        return target, 443

    def parse_http_target(self, data):
        headers = data.decode("latin-1", "replace").split("\r\n")
        host_header = ""
        for header in headers:
            if header.lower().startswith("host:"):
                host_header = header.split(":", 1)[1].strip()
                break
        if not host_header:
            raise ValueError("Host başlığı yok")
        if ":" in host_header and not host_header.startswith("["):
            host, port = host_header.rsplit(":", 1)
            return host, int(port)
        return host_header.strip("[]"), 80

    def tunnel(self, client, upstream, fragment_client):
        client.setblocking(False)
        upstream.setblocking(False)
        sockets = [client, upstream]
        client_fragment_budget = 4096 if fragment_client else 0
        while self.running.is_set():
            readable, _, errored = select.select(sockets, [], sockets, 1)
            if errored:
                break
            for sock in readable:
                other = upstream if sock is client else client
                try:
                    data = sock.recv(65535)
                    if not data:
                        return
                    if sock is client and client_fragment_budget > 0:
                        take = min(len(data), client_fragment_budget)
                        self.send_fragmented(other, data[:take])
                        if take < len(data):
                            other.sendall(data[take:])
                        client_fragment_budget -= take
                    else:
                        other.sendall(data)
                except OSError:
                    return

    def send_fragmented(self, sock, data, size=8, pause=0.003):
        for index in range(0, len(data), size):
            sock.sendall(data[index:index + size])
            time.sleep(pause)


class NetworkProfile:
    def __init__(self):
        self.runner = Runner()
        self.proxy_profile = WindowsProxyProfile()
        self.proxy = FragmentingProxy()

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

    def enable_dns(self):
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

    def enable(self):
        adapters = self.enable_dns()
        self.proxy.start()
        self.proxy_profile.enable()
        return adapters

    def restore(self):
        self.proxy_profile.restore()
        self.proxy.stop()
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
            with urlopen(request, timeout=12) as response:
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
        self.geometry("760x560")
        self.minsize(660, 500)
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

        ttk.Label(shell, text="SİSTEM GENELİ ERİŞİM PROFİLİ", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Tek tuşla DPI kırma modu", style="Title.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            shell,
            text="DNS'i değiştirir, Windows sistem proxy'sini açar ve yerel proxy üstünden TLS başlangıcını küçük parçalara böler. Sadece Roblox değil, sistem proxy'sini kullanan bütün uygulamalar için çalışır.",
            style="Body.TLabel",
            wraplength=660,
        ).pack(anchor="w", pady=(10, 24))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 20))

        self.main_button = ttk.Button(actions, text="Erişim engelini aç", style="Action.TButton", command=self.enable_profile)
        self.main_button.pack(side="left")
        self.restore_button = ttk.Button(actions, text="Tamamen geri al", style="Ghost.TButton", command=self.restore_profile)
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
            self.status.configure(text="Bu sürüm Windows için hazırlandı.")
            self.log("Windows dışında sistem DNS ve proxy ayarı yapmam.")
            self.main_button.configure(state="disabled")
            self.restore_button.configure(state="disabled")
            return
        if not is_admin():
            self.status.configure(text="Yönetici izni gerekiyor.")
            self.log("DNS, WinHTTP ve sistem proxy ayarı için yönetici izni lazım.")
            self.main_button.configure(text="Yönetici olarak aç", command=self.elevate)
            return
        self.status.configure(text="Hazır. Butona basınca sistem proxy modu açılacak.")
        self.log("Yönetici izni tamam. DNS, WinHTTP ve kullanıcı proxy profilini değiştirebilirim.")

    def elevate(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Yönetici olarak açılamadı:\n{exc}")

    def run_background(self, target):
        self.set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def enable_profile(self):
        if not is_admin():
            self.elevate()
            return

        def work():
            try:
                self.safe_status("Sistem geneli erişim profili açılıyor")
                adapters = self.profile.enable()
                self.log(f"DNS ayarlandı: {', '.join(adapters)}")
                self.log(f"Yerel DPI kırma proxy'si açıldı: {PROXY_HOST}:{PROXY_PORT}")
                self.log("Windows kullanıcı proxy'si ve WinHTTP proxy bu porta yönlendirildi.")
                self.log("Not: Bazı oyun istemcileri sistem proxy'sini dinlemez. Onlar için sürücü tabanlı mod gerekir.")
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
                self.safe_status("Tüm ağ ayarları geri alınıyor")
                adapters = self.profile.restore()
                self.log(f"Proxy kapatıldı, DNS otomatiğe döndü: {', '.join(adapters)}")
                self.safe_status("Geri alındı. Eski ağ profilindesin.")
            except Exception as exc:
                self.safe_status("Geri alma başarısız")
                self.log(f"Hata: {exc}")
                messagebox.showerror(APP_NAME, str(exc))
            finally:
                self.set_busy(False)

        self.run_background(work)

    def check_connectivity(self):
        self.safe_status("Bağlantılar kontrol ediliyor")
        for host, ok in self.profile.resolve_report():
            self.log(f"{'OK' if ok else 'FAIL'}  {host}")
        if self.profile.http_probe():
            self.log("OK  Roblox web yanıt verdi")
            self.safe_status("Bitti. Pencere açık kaldığı sürece erişim modu aktif.")
        else:
            self.log("Uyarı: Roblox web testi yanıt vermedi. Bu ağda sürücü tabanlı mod gerekebilir.")
            self.safe_status("Profil aktif, ama test net değil. Sıradaki adım sürücü modu.")

    def open_link(self, name):
        import webbrowser
        webbrowser.open(QUICK_LINKS[name])

    def on_close(self):
        if messagebox.askyesno(APP_NAME, "Pencere kapanınca yerel proxy durur. Ağ ayarlarını geri alıp kapatayım mı?"):
            try:
                self.profile.restore()
            except Exception:
                pass
            self.destroy()

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
