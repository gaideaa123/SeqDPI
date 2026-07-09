# SeqDPI

SeqDPI, Türkiye için tek butonlu Windows DPI yardımcı uygulaması.

Bu sürüm çalışan çekirdeği bozmadan paketlemeyi düzeltir: uygulama artık **SeqDPI.exe** olarak, **pencereli modda** ve **CMD konsolu göstermeden** üretilecek şekilde hazırlanmıştır.

## Çalıştırma

Geliştirme için:

```powershell
python seqdpi.py
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
- Windows sürüm bilgisi: `version_info.txt`
- GitHub Actions artifact: `SeqDPI-windows-exe`

## Not

Çalışan ağ/DPI mantığına dokunulmadı. Bu PR sadece dağıtım, isimlendirme ve CMD görünmeden çalışma tarafını cilalar.
