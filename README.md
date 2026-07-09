# SeqDPI

SeqDPI, Türkiye koşullarına göre ayarlanmış tek butonlu Windows DPI atlatma GUI'si.

Araştırma sonucu düzeltme: sadece DNS değiştirmek veya sadece upstream GoodbyeDPI `-9` çalıştırmak yetmiyor. Türkiye'de bazı ISS'ler DNS'i zehirliyor veya kesiyor, Chrome/Edge QUIC/HTTP3 ile TCP tarafındaki DPI atlatmayı boşa çıkarabiliyor, Chromium Kyber ise TLS ClientHello paketini büyütüp bazı GoodbyeDPI modlarını kırabiliyor.

## Yeni çalışma şekli

- Resmi `cagritaskn/GoodbyeDPI-Turkey` release paketini indirir
- WinDivert tabanlı `goodbyedpi.exe` motorunu çalıştırır
- Varsayılan olarak Türkiye DNS redirection modu kullanır
- DNS isteklerini non-standard porttaki resolvere yönlendirir
- UDP 443 çıkışını firewall ile kapatıp QUIC/HTTP3'ü devre dışı bırakır
- Chrome ve Edge için Kyber/PostQuantumKeyAgreement policy değerini kapatır
- HTTP testlerinde 403/404 gibi siteye ulaşıldığını gösteren cevapları artık yanlışlıkla FAIL saymaz
- Tek butonla motoru durdurur, DNS'i otomatiğe alır, firewall kuralını kaldırır

## Modlar

1. Türkiye DNS redir: `-9` + DNS redirection
2. SNI parçalama: manual modern mode + `--frag-by-sni`
3. Uyumlu mod: `-7` + DNS redirection
4. Eski uyumlu mod: `-2` + DNS redirection

## Çalıştırma

Windows üzerinde Python 3.11 veya üstü:

```powershell
python seqdpi.py
```

Yönetici izni gerekir. İlk çalıştırmada motor `%APPDATA%/SeqDPI/engine` altına indirilir.

## Exe üretme

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SeqDPI seqdpi.py
```
