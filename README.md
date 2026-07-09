# SeqDPI

SeqDPI, Türkiye için tek tık Windows DPI yardımcı uygulaması.

## Kullanıcıya verilecek dosya

```text
SeqDPI-Setup.exe
```

Kullanıcı bunu açar, Next der, masaüstüne **SeqDPI** gelir. Build klasörü, dist klasörü, Python, Inno Setup görmez.

## Installer görünümü

Setup artık klasik beyaz kurulum ekranı değil:

- Koyu neon SeqDPI teması
- Üst bar görsel olarak sayfayla birleşik, bitmap gizli
- Daha temiz welcome ve finish metinleri
- Next akışı özellikle sade tutuldu

## Son hata düzeltmesi

Inno Setup aynı dosyada `ignoreversion` ve `replacesameversion` bayraklarını birlikte kabul etmiyor. `SeqDPI.exe` için artık sadece geçerli bayraklar kullanılıyor:

```text
replacesameversion restartreplace uninsrestartdelete
```

## Setup üretmek

```powershell
./build_installer.ps1
```

Çıktı:

```text
dist/installer/SeqDPI-Setup.exe
```
