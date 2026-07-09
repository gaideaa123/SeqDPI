# SeqDPI

SeqDPI, Türkiye için tek butonlu Windows DPI yardımcı uygulaması.

Bu sürüm çalışan ağ çekirdeğini bozmadan arayüzü yeniler: neon renkli, animasyonlu, CMD göstermeyen, tek dosya **SeqDPI.exe**.

## Yeni GUI

- Animasyonlu neon arka plan
- Büyük tek tuş açma alanı
- Canlı durum halkası
- Renkli canlı günlük
- Erişimi aç, sıradaki yöntem, test ve kapat aksiyonları
- Roblox ve Discord hızlı butonları
- Konsolsuz `SeqDPI.pyw` launcher

## Çalıştırma

Geliştirme için:

```powershell
python seqdpi.py
```

Yeni konsolsuz GUI:

```powershell
pythonw SeqDPI.pyw
```

Exe üretmek için:

```powershell
./build_exe.ps1
```

Çıktı:

```text
dist/SeqDPI.exe
```

## Exe özellikleri

- Dosya adı: `SeqDPI.exe`
- Konsol yok: PyInstaller `--windowed`
- Yönetici izni ister: PyInstaller `--uac-admin`
- Tek dosya: PyInstaller `--onefile`
- GitHub Actions artifact: `SeqDPI-windows-exe`

## Not

Çalışan DPI/DNS mantığına dokunulmadı. Yeni GUI `seqdpi.py` içindeki sağlam çekirdeği import eder.
