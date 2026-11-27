# Motor font ve yazı testi

`studio/public/font-writing-test/Motor_Test.json` beyaz zeminli, 1920×1080,
30 FPS ve 103 saniyelik yedi sahne içerir. İlk dört sahne CSS tipografisini,
son üç sahne sırayla GLYPHS, Be Vietnam Pro 600 ve matematiksel formül
vuruşlarını gösterir.

Kaggle'da bu dalı aldıktan sonra mevcut Remotion girişini çalıştırın.

```bash
cd studio
npm ci
npm run render -- C /kaggle/working/Motor_Font_Test.mp4 \
  '--props={"videoId":"font-writing-test","timelineFile":"Motor_Test.json"}'
```

Kaggle imajında Chromium veya Chrome kuruluysa kullanılacak yürütülebilir
dosyayı `--browser-executable` ile belirtin. Test girdileri depoda hazırdır.
Planı tekrar oluşturmak için npm ve Python bağımlılıklarını kurduktan sonra
depo kökünden `python scripts/build-font-test.py` çalıştırın.

Be Vietnam Pro'nun gerçek Latin 600 WOFF dosyası glif şeklini ve karakter
genişliğini sağlar. `engine/font_pen.py` örnek metindeki 30 farklı karakter
için elle tanımlanmış, sıralı kalem yollarını ayrı tutar. Yol ilerledikçe
motorun mevcut `penPaint` maskelemesi yalnızca o glifin mürekkebini açar.
Maske ve el aynı vuruş ilerlemesini kullanır. Yeni karakterlerin eklenmesi
kendi vuruş verilerini gerektirir.
