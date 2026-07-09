# SeqDPI

## En güncel arkadaş build'i

Bu branch arkadaşın bilgisayarı için en güvenli mantığı hedefler:

- DNS'e public resolver dayatmaz
- DNS başarısızsa bile motoru denemeye devam eder
- Ping artmasın diye önce sadece hedef domainlere uygulanan modlar kullanılmalı
- Roblox ve Discord dışı oyun trafiğine dokunulmamalı
- Global DPI modları sadece son çare olmalı

## Ping sorunu neden olur?

GoodbyeDPI/WinDivert tüm trafiğe uygulanırsa bazı oyunlarda lag spike veya ping artışı olabilir. Çözüm, sistemi komple kurcalamak değil, sadece engelli hedeflerin ilk bağlantı paketlerini hedeflemektir.

## Arkadaşa verilecek dosya

Sadece:

```text
SeqDPI-Setup.exe
```

Eski sürüm yüklüyse önce kaldırıp yeni setup ile kurması daha temiz olur.
