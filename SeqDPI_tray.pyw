import os
import runpy
import sys
import threading
import time


def resource_path(name):
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)
    roots.extend([os.path.dirname(os.path.abspath(__file__)), os.getcwd()])
    for root in roots:
        path = os.path.join(root, name)
        if os.path.exists(path):
            return path
    return name


def load_gui_class():
    gui_path = resource_path("SeqDPI.pyw")
    namespace = runpy.run_path(gui_path, run_name="seqdpi_gui_loaded")
    return namespace["SeqDPIApp"]


BaseSeqDPIApp = load_gui_class()


class TraySeqDPIApp(BaseSeqDPIApp):
    def __init__(self):
        self.tray_icon = None
        self.tray_ready = False
        super().__init__()
        self.setup_tray()
        self.bind("<Map>", self._restore_frameless, add="+")

    def setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:
            self.logger("Tray desteği yok, normal küçültme kullanılacak.")
            return

        image = Image.new("RGBA", (64, 64), (18, 13, 32, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 6, 58, 58), outline=(255, 79, 216, 255), width=5)
        draw.ellipse((14, 14, 50, 50), outline=(57, 217, 255, 255), width=4)
        draw.line((32, 17, 32, 35), fill=(255, 247, 223, 255), width=7)
        draw.arc((20, 24, 44, 48), 130, 410, fill=(255, 247, 223, 255), width=6)

        self.tray_icon = pystray.Icon(
            "SeqDPI",
            image,
            "SeqDPI",
            menu=pystray.Menu(
                pystray.MenuItem("Aç", lambda _icon, _item: self.after(0, self.show_from_tray)),
                pystray.MenuItem("Gizle", lambda _icon, _item: self.after(0, self.hide_to_tray)),
                pystray.MenuItem("Motoru kapat", lambda _icon, _item: self.after(0, self.stop_engine_only)),
                pystray.MenuItem("Çıkış", lambda _icon, _item: self.after(0, self.quit_from_tray)),
            ),
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.tray_ready = True
        self.logger("Tray aktif. X veya küçültme pencereyi gizler, uygulama görev çubuğundan geri açılır.")

    def _restore_frameless(self, _event=None):
        try:
            self.after(120, lambda: self.overrideredirect(True))
        except Exception:
            pass

    def show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.overrideredirect(True)
        except Exception:
            pass

    def hide_to_tray(self):
        if self.tray_ready:
            self.withdraw()
            return
        try:
            self.overrideredirect(False)
            self.iconify()
            self.after(250, lambda: self.overrideredirect(True))
        except Exception:
            self.withdraw()

    def iconify_window(self):
        self.hide_to_tray()

    def on_close(self):
        self.hide_to_tray()

    def stop_engine_only(self):
        def worker():
            try:
                self.engine.stop_all()
                self.logger("Motor kapatıldı. Pencere tray'de kalıyor.")
                self.set_status("kapalı", "#ff9f43")
            except Exception as exc:
                self.logger(f"Kapatma hatası: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def quit_from_tray(self):
        def worker():
            try:
                self.engine.stop_all()
            except Exception:
                pass
            try:
                if self.tray_icon:
                    self.tray_icon.stop()
            except Exception:
                pass
            self.after(0, self.destroy)
        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    TraySeqDPIApp().mainloop()
