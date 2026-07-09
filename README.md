# SeqDPI

SeqDPI, Türkiye için tek tık Windows DPI yardımcı uygulaması.

## Kullanıcıya verilecek dosya

```text
SeqDPI-Setup.exe
```

Kullanıcı bunu açar, Next der, masaüstüne **SeqDPI** gelir. Build klasörü, dist klasörü, Python, Inno Setup görmez.

## Installer notu

Setup başlamadan önce eski SeqDPI ve GoodbyeDPI süreçlerini kapatır, GoodbyeDPI servisini siler ve WinDivert kilitlerini best-effort durdurur. Böylece eski `SeqDPI.exe` veya motor açıkken yeniden kurulumda çıkan `Delete failed, code 5, Access denied` hatası engellenir.

## Sesler

- `hello.mp3`: program ilk açıldığında arka planda çalar
- `dns.mp3`: sağlıklı yöntem bağlanınca arka planda çalar

Bu iki dosya varsa PyInstaller otomatik exe içine paketler.

## Setup üretmek

```powershell
./build_installer.ps1
```

Çıktı:

```text
dist/installer/SeqDPI-Setup.exe
```
