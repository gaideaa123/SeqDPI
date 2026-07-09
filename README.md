# SeqDPI

SeqDPI, Türkiye için tek butonlu GoodbyeDPI-Turkey GUI'si.

Bu sürüm DNS'i öldüren `dnsredir` metodlarını başarı sayma hatasını düzeltir. Kullanıcı logunda `service_install_dnsredir_turkey` başarıyla çalışmasına rağmen tüm alan adları `getaddrinfo failed` dönüyordu. Araştırmada bunun bilinen sınıf olduğu görüldü: `dnsredir` 77.88.8.8:1253 gibi non-standard DNS porta yönlendirir, bazı ağlarda veya güvenlik yazılımlarında bu yol tüm DNS'i kesebilir.

## Ne değişti?

- Önce çalışan DNS profili kurulur: Cloudflare, olmazsa Google, olmazsa Yandex
- `dnsredir` içeren metodlar artık en sona atılır
- Manuel `goodbyedpi.exe -9/-8/-7...` no-dnsredir modları önce denenir
- Her metod başlatıldıktan sonra DNS sağlık kontrolünden geçer
- DNS ölürse metod kapatılır, DNS tekrar düzeltilir ve sıradaki metoda geçilir
- Servis başarılı görünse bile DNS bozuksa başarısız sayılır
- `dnsredir` scriptleri sadece fallback olarak denenir
- Test raporu artık önce DNS sağlık skorunu, sonra HTTP sonuçlarını basar

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
