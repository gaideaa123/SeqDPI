# SeqDPI

SeqDPI, Windows için tek butonlu bir erişim profili uygulaması. GUI üzerinden aktif ağ adaptörlerinin DNS ayarını Cloudflare DNS'e çeker, DNS önbelleğini temizler ve Roblox ile Discord bağlantılarını kontrol eder.

## Özellikler

- Tek butonla DNS profilini uygular
- Yönetici izni yoksa kendini UAC ile yeniden açar
- Aktif ağ adaptörlerini otomatik bulur
- IPv4 ve IPv6 DNS sunucularını ayarlar
- DNS önbelleğini temizler
- Roblox ve Discord için hızlı bağlantı kontrolü yapar
- İstersen tek tıkla eski otomatik DNS ayarına döner

## Çalıştırma

Windows üzerinde Python 3.11 veya üstü yeterli.

```powershell
python seqdpi.py
```

Uygulama sistem DNS ayarlarını değiştirdiği için yönetici izni ister.

## Tek dosya exe üretme

İstersen PyInstaller ile tek dosyalık exe alabilirsin:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SeqDPI seqdpi.py
```

Çıktı `dist/SeqDPI.exe` altında oluşur.

## Not

Bu sürüm DNS tabanlı erişim sorunlarını hedefler. Operatör tarafında DNS dışı filtreleme varsa bağlantı testi uyarı verebilir. Bu durumda bir sonraki adım Windows paket katmanı entegrasyonu olur.
