# SeqDPI

SeqDPI, Türkiye için tek butonlu GoodbyeDPI-Turkey runtime GUI'si.

Bu sürüm özellikle önceki hatayı düzeltir: uygulama yanlışlıkla upstream `goodbyedpi-0.2.2` paketini yeniden kullanıyordu ve Russia scriptlerini en üste koyuyordu. Ayrıca batch dosyaları uzun süre açık kalmak için tasarlandığından `subprocess.run(... timeout=25)` ile çalıştırmak hataydı.

## Araştırmaya göre doğru akış

GoodbyeDPI-Turkey README'si iki kullanım öneriyor:

- Tek seferlik kullanım: `turkey_dnsredir.cmd`
- Servis kurulumu: `service_install_dnsredir_turkey.cmd`
- SuperOnline alternatifleri: `turkey_dnsredir_alternative(1-6)_superonline.cmd`

Bu yüzden yeni sürüm:

- Eski engine klasörünü Turkey marker yoksa siler
- Zorla `goodbyedpi-0.2.3rc3-turkey.zip` release assetini indirir
- `turkey_dnsredir.cmd` yoksa başlamaz, yani yanlış paketi kabul etmez
- Russia ve blacklist scriptlerini filtreler
- Önce `turkey_dnsredir.cmd` çalıştırır
- Sonra SuperOnline alternatif runtime scriptlerini dener
- Servis scriptlerine gerekirse Enter otomatik gönderir
- Runtime scriptleri için timeout kullanmaz, 3 saniye sonra süreç hâlâ yaşıyorsa başarı sayar
- Motor hemen kapanırsa runtime logunu gösterir
- QUIC/HTTP3 için UDP 443 firewall kuralı ekler
- Chrome/Edge Secure DNS ve Kyber policy değerlerini kapatır
- Kapatırken `service_remove.cmd`, `taskkill`, firewall temizliği ve DNS restore çalıştırır

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
