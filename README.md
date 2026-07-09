# SeqDPI

## Friend-safe DNS mode

Bu sürüm arkadaşının ağındaki hatayı hedefler: public DNS profilleri otomatik yazılmaz.

Ne değişti:

- Cloudflare, Google, Yandex DNS artık başlangıçta zorla denenmez
- Önce mevcut DNS korunur
- Mevcut DNS doğrulanamazsa sadece otomatik/DHCP DNS'e dönmeyi dener
- DNS yine doğrulanamazsa program durmaz, DPI metodlarını çalıştırmaya devam eder
- Kapatırken kullanıcının DNS ayarını gereksiz yere bozmaz
- DNS artık başarı kapısı değil, sadece teşhis sinyali

Bu özellikle public DNS'i bloklayan modem/ISS/güvenlik yazılımı olan bilgisayarlarda daha güvenlidir.
