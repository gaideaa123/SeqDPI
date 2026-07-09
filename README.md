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
- GoodbyeDPI-Turkey motorunu setup içine paketler
- İlk açılışta ayrıca motor indirmeye gerek kalmaz
- Kullanıcı build/dist klasörü görmez

## Geliştirici komutları

Setup üretmek için tek komut:

```powershell
./build_installer.ps1
```

Script önce `SeqDPI.exe` üretir, sonra Inno Setup yoksa otomatik kurmayı dener, ardından installer üretir.

Çıktılar:

```text
dist/SeqDPI.exe
dist/installer/SeqDPI-Setup.exe
```

## Inno Setup elle kurulacaksa

Aynı satıra `veya` yazma. Şunlardan sadece birini çalıştır:

```powershell
winget install --id JRSoftware.InnoSetup --exact
```

veya Chocolatey kuruluysa:

```powershell
choco install innosetup -y
```

## Not

Çalışan DPI/DNS çekirdeğine dokunulmadı. Bu PR sadece installer build deneyimini daha kolay yapar.
