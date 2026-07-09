# SeqDPI

## Discord fix

Bu sürüm Roblox çalışırken Discord'un web ve uygulama tarafında kalmasını düzeltmek için başarı kriterini değiştirdi.

Önceden metod sadece DNS sağlamsa başarılı sayılıyordu. Artık Discord özel sağlık kontrolü var:

- `discord.com`
- `gateway.discord.gg`
- `updates.discord.com`
- `cdn.discordapp.com`
- `discordapp.com / discordapp.net / discord.gg`

Ayrıca Discord hedefli blacklist dosyası oluşturulup önce `discord targeted -9/-8/-7...` modları deneniyor. Bir metod Discord web, gateway, update ve CDN testlerinden geçmezse kapatılıp sıradaki metoda geçiliyor.

## Kullanıcı akışı

Kullanıcı yine sadece `SeqDPI-Setup.exe` alır, kurar, masaüstündeki SeqDPI'yi açar ve tek tuşa basar.
