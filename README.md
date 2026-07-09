# SeqDPI

## Tray + tkinter fix

Tray launcher artık `tkinter`, `_tkinter`, `tkinter.ttk`, `seqdpi`, `pystray` ve `Pillow` bağımlılıklarını açıkça import eder. Çünkü `SeqDPI.pyw` dinamik olarak `runpy` ile yüklendiğinde PyInstaller tkinter bağımlılığını göremiyordu.

Bu düzeltme şu hatayı hedefler:

```text
ModuleNotFoundError: No module named 'tkinter'
```

## Davranış

- X tuşu uygulamayı kapatmaz, tray'e gizler
- Küçült tuşu tray'e gizler
- Tray menüsünden Aç, Gizle, Motoru kapat, Çıkış yapılır

## Build

```powershell
./build_installer.ps1
```

Kullanıcıya yine sadece:

```text
SeqDPI-Setup.exe
```
