# SeqDPI

SeqDPI, Türkiye için tek butonlu GoodbyeDPI-Turkey runtime GUI'si.

Bu sürüm WinError 32 kilitlenmesini kökten çözer. Eski buildler `%APPDATA%/SeqDPI/engine` klasörünü kullanıyordu. Windows'ta bir `cmd.exe`, `goodbyedpi.exe` veya WinDivert süreci bu klasörü çalışma dizini olarak tutarsa `shutil.rmtree` klasörü silemez ve `[WinError 32]` verir. Yeni sürüm o klasöre bağlı kalmaz.

## Ne düzeldi?

- Eski `%APPDATA%/SeqDPI/engine` artık kullanılmaz
- Yeni Turkey motoru `%APPDATA%/SeqDPI/engine-turkey-current` altına iner
- Legacy engine kilitliyse hata verilmez, dokunmadan geçilir
- Legacy engine silinebiliyorsa temizlenir, silinemiyorsa yeniden başlatmada silinmek üzere işaretlenir
- `goodbyedpi.exe` süreçleri ve SeqDPI engine klasörünü tutan eski `cmd.exe` süreçleri kapatılır
- GoodbyeDPI servisi ve WinDivert servis kilitleri best-effort durdurulur
- Runtime batch dosyaları timeout ile öldürülmez
- Turkey dışı Russia/blacklist scriptleri filtrelenir

## Kullanım

```powershell
python seqdpi.py
```

Yönetici izni gerekir.

## Exe üretme

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SeqDPI seqdpi.py
```

Log dosyası: `%APPDATA%/SeqDPI/seqdpi.log`
