# SeqDPI

SeqDPI, Windows için tek butonlu sistem geneli erişim profili uygulaması. DNS'i Cloudflare üstüne alır, Windows kullanıcı proxy'sini ve WinHTTP proxy ayarını yerel SeqDPI proxy'sine yönlendirir. Yerel proxy, TLS bağlantı başlangıcını küçük parçalara bölerek basit DPI kontrollerini atlatmayı dener.

## Özellikler

- Tek butonla sistem proxy modu
- Cloudflare IPv4 ve IPv6 DNS profili
- Yerel HTTP/HTTPS CONNECT proxy
- TLS ClientHello parçalama
- WinINet ve WinHTTP proxy ayarı
- Roblox, Discord ve genel HTTPS siteleri için bağlantı kontrolü
- Tek butonla DNS ve proxy ayarlarını geri alma

## Çalıştırma

Windows üzerinde Python 3.11 veya üstü yeterli.

```powershell
python seqdpi.py
```

Uygulama sistem DNS, kullanıcı proxy ve WinHTTP proxy ayarlarını değiştirdiği için yönetici izni ister.

## Önemli not

Bu sürüm sistem proxy'sini kullanan uygulamalar için çalışır. Tarayıcılar, Discord ve birçok masaüstü uygulaması bunu dinler. Bazı oyun istemcileri ve kernel seviyesinde ağ kullanan programlar Windows proxy ayarını yok sayabilir. O sınıf için bir sonraki adım sürücü tabanlı WinDivert/WFP modu olur.

## Tek dosya exe üretme

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SeqDPI seqdpi.py
```

Çıktı `dist/SeqDPI.exe` altında oluşur.
