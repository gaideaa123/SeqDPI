# SeqDPI

## Tray davranışı

Son sürümde pencere artık arkada rahatsız etmez:

- X tuşu uygulamayı kapatmaz, tray'e gizler
- Küçült tuşu tray'e gizler
- Tray menüsünden tekrar açılabilir
- Tray menüsünden sadece motor kapatılabilir
- Tray menüsünden tamamen çıkış yapılabilir

## Build

```powershell
./build_installer.ps1
```

Build artık `pystray` ve `pillow` paketlerini kurar, `SeqDPI_tray.pyw` launcher'ını paketler.

Kullanıcıya yine sadece şunu ver:

```text
SeqDPI-Setup.exe
```
