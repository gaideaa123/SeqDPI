# SeqDPI

SeqDPI, Türkiye için tek tık Windows DPI yardımcı uygulaması.

## Kullanıcıya verilecek dosya

```text
SeqDPI-Setup.exe
```

Kullanıcı bunu açar, Next der, masaüstüne **SeqDPI** gelir. Build klasörü, dist klasörü, Python, Inno Setup görmez.

## Sesler

- `hello.mp3`: program ilk açıldığında arka planda çalar
- `dns.mp3`: sağlıklı yöntem bağlanınca arka planda çalar

Bu iki dosya varsa PyInstaller otomatik exe içine paketler.

## Setup üretmek

```powershell
./build_installer.ps1
```

Script şunları yapar:

1. `SeqDPI.exe` üretir
2. `hello.mp3` ve `dns.mp3` varsa exe içine koyar
3. GoodbyeDPI-Turkey motorunu setup içine paketler
4. Inno Setup yoksa otomatik kurmayı dener
5. `dist/installer/SeqDPI-Setup.exe` üretir

## Inno Setup elle kurulacaksa

Sadece bunu çalıştır:

```powershell
winget install --id JRSoftware.InnoSetup --exact
```

`veya choco...` aynı satıra yazılmayacak. O kelime komut değil.
