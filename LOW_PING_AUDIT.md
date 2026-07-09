# SeqDPI low-ping audit

Araştırma sonucu: ping/lag sorununun ana sebebi genelde WinDivert'in tüm trafiği filtrelemesi veya agresif global presetlerin oyun/anti-cheat trafiğine dokunmasıdır. Bu yüzden arkadaş modu için güvenli kural şu:

## Kesin kurallar

- Public DNS zorlanmaz.
- DNS doğrulanmadı diye program durmaz.
- `dnsredir` otomatik ilk seçenek olmaz.
- Global GoodbyeDPI modları en son çare olur.
- Önce sadece Discord ve Roblox host listesine uygulanan blacklist/targeted modlar denenir.
- QUIC engeli sadece HTTP3 kaçışını kesmek içindir, oyun UDP portlarına dokunulmaz.
- Sağlık testleri fail verse bile çalışan motor hemen öldürülmez, çünkü bazı ağlarda test false negative dönebilir.

## Arkadaş build'i için önerilen branch sırası

1. `feature/friend-safe-no-dns-hardfail`
2. Bu branch üstüne low-ping davranış
3. Setup artifact: `SeqDPI-Setup.exe`

## Neden bu en güvenlisi?

Arkadaşın ağı public DNS'i blokluyor gibi görünüyor. Bu yüzden DNS yazmak yerine mevcut ağı koruyup, sadece erişim engeli olan domainlerin DPI imzasını bozmak en düşük pingli yoldur.
