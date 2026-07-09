# SeqDPI

SeqDPI, Türkiye için tek tık Windows DPI yardımcı uygulaması.

Kullanıcı tarafında hedef akış basit: **SeqDPI-Setup.exe** açılır, Next denir, kurulum biter, masaüstüne **SeqDPI** gelir. Kullanıcı sonra masaüstündeki kısayola basar ve neon GUI açılır.

## Kullanıcıya verilecek dosya

```text
SeqDPI-Setup.exe
```

Bu dosya GitHub Actions artifact olarak `SeqDPI-Setup` adıyla üretilir.

## Kurulum deneyimi

- Modern setup sihirbazı
- Yönetici izni ister
- `Program Files\SeqDPI` altına kurar
- Masaüstüne `SeqDPI` kısayolu ekler
- Başlat menüsüne `SeqDPI` ekler
- İsterse kurulum bitince uygulamayı açar
- Kullanıcı build/dist klasörü görmez

## Geliştirici komutları

Sadece exe üretmek:

```powershell
./build_exe.ps1
```

Setup üretmek:

```powershell
./build_installer.ps1
```

Çıktılar:

```text
dist/SeqDPI.exe
dist/installer/SeqDPI-Setup.exe
```

## Gerekli araçlar

Yerel installer build için Inno Setup gerekir:

```powershell
winget install JRSoftware.InnoSetup
```

veya:

```powershell
choco install innosetup -y
```

GitHub Actions bunu otomatik kurar.

## Not

Çalışan DPI/DNS çekirdeğine dokunulmadı. Bu PR sadece kullanıcı dostu kurulum deneyimi ekler.
