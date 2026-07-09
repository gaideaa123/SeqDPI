# SeqDPI

## Discord invalid session fix

Bu sürüm Discord tarafında görülen `[SSL: INVALID_SESSION_ID]` probe hatasını düzeltir.

Ne değişti:

- Discord için agresif `-7/-8/-9` yerine önce daha uyumlu `-2`, `-1`, `-4` denenir
- Health check önce Windows `curl.exe` ile yapılır, Python OpenSSL'in false negative hatasına takılmaz
- Python fallback içinde TLS session ticket kapatılır
- `INVALID_SESSION_ID` artık doğrudan metod başarısızlığı sayılmaz, TLS'in hedefe ulaştığı sinyal olarak loglanır
- Discord web, gateway, update ve CDN kontrolleri yine korunur

Kısaca: Roblox çalışırken Discord'u öldüren agresif fragmentation daha geç denenir, Discord için daha uyumlu modlar öne alınır.
