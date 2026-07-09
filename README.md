# SeqDPI

SeqDPI, Türkiye için tek tık Windows DPI yardımcı uygulaması.

## Son düzeltmeler

- Kurulum sonunda uygulamayı açarken çıkan `CreateProcess failed, code 740` düzeltildi
- Setup artık postinstall launch için `runascurrentuser` kullanır
- Uygulama GUI'si frameless, özel sürüklenebilir üst barlı ve daha minimal neon tasarımlı
- Native Windows title bar yerine yarı saydam görünen özel kontrol barı var
- Installer ekranı koyu neon tema ve özel welcome metinleriyle cilalandı

## Kullanıcıya verilecek dosya

```text
SeqDPI-Setup.exe
```

Kullanıcı bunu açar, Next der, masaüstüne **SeqDPI** gelir.

## Setup üretmek

```powershell
./build_installer.ps1
```

Çıktı:

```text
dist/installer/SeqDPI-Setup.exe
```
