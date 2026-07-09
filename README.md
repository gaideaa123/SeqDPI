# SeqDPI

SeqDPI, Türkiye için tek butonlu GoodbyeDPI launcher GUI'si.

Bu sürümde önceki hatanın kökü düzeltildi: uygulama artık kafadan argüman üretmiyor. `GoodbyeDPI-Turkey` release paketini indiriyor, içindeki gerçek `.cmd` / `.bat` metodlarını keşfediyor, önce en olası Türkiye DNS redirection servis scriptini çalıştırıyor, olmazsa sıradaki yöntemlere geçiyor. Motor kapanırsa artık sessizce “kapandı” demiyor, gerçek stdout/stderr çıktısını loga basıyor.

## Ne değişti?

- Release içindeki scriptler otomatik keşfedilir
- `service_install`, `dnsredir`, `turkey`, `alternative`, `superonline` isimlerine göre yöntem sıralanır
- Desteklenmeyen argüman basma hatası kaldırıldı
- `goodbyedpi.exe -h` çıktısı okunup sadece desteklenen manuel fallbackler oluşturulur
- Motor hemen kapanırsa hata çıktısı kullanıcıya gösterilir
- QUIC/HTTP3 UDP 443 firewall kuralı eklenir
- Chrome/Edge Secure DNS policy kapatılır
- Chrome/Edge Kyber policy kapatılır
- DNS Cloudflare'a alınır, DNS önbelleği temizlenir
- Kapatırken service remove scriptleri aranır, kalan `goodbyedpi.exe` süreçleri kapatılır, DNS geri alınır
- Log `%APPDATA%/SeqDPI/seqdpi.log` altında tutulur

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

## Not

Türkiye'deki ISS davranışı sabit değil. Bu yüzden tek bir hardcoded preset yerine gerçek paket metodlarını sırayla deneyen launcher daha sağlamdır.
