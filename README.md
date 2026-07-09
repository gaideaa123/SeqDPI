# SeqDPI

SeqDPI artık proxy denemesi değil, Windows paket seviyesinde sistem modu açan tek butonlu bir GUI.

Araştırma sonucu net: GoodbyeDPI tarayıcı proxy'si gibi çalışmıyor. WinDivert sürücüsüyle TCP paketlerini yakalıyor ve DPI cihazlarının gördüğü paketleri bozarken gerçek hedef sunucunun bağlantıyı kabul etmesini sağlıyor. Bu yüzden sistem proxy'sini yok sayan oyun istemcileri için de doğru yön bu.

## Ne yapar?

- GoodbyeDPI'nin son resmi release paketini indirir
- `goodbyedpi.exe` motorunu WinDivert ile yönetici olarak çalıştırır
- En güçlü hazır preset olan `-9` ile başlar
- Çalışmazsa GUI'den `-8` ve `-7` alternatiflerine geçebilir
- DNS'i Cloudflare IPv4/IPv6 üstüne alır
- DNS önbelleğini temizler
- Roblox, Discord ve genel HTTPS çözümlemesini kontrol eder
- Tek butonla motoru durdurur ve DNS'i otomatiğe döndürür

## Çalıştırma

Windows üzerinde Python 3.11 veya üstü:

```powershell
python seqdpi.py
```

Yönetici izni gerekir. İlk çalıştırmada GoodbyeDPI motoru `%APPDATA%/SeqDPI/engine` altına indirilir.

## Exe üretme

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SeqDPI seqdpi.py
```

## Notlar

- Bu sürüm sistem proxy'si değil, WinDivert tabanlı paket yakalama kullanır.
- Erişim engeli DPI tabanlıysa önce `Sistem geneli`, sonra `Alternatif 1`, sonra `Alternatif 2` denenmeli.
- Roblox erişimi bazı dönemlerde DNS, IP, TLS SNI ve uygulama istemcisi davranışına göre değişebiliyor. Bu yüzden tek DNS değişikliği yetmez.
