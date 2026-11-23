# Yazı ve illüstrasyon testi

| Özellik | Durum | Kapsam |
|---|---|---|
| Merkez vuruşlu el yazısı | PASS | Üç örnek metinde okunabilir vuruşlar, görünen satır düzeni ve kalem kaldırma test edildi. |
| Kalem ve çizgi eşzamanlılığı | PASS | Tarayıcıda örneklenen etkin yol uçları PNG üzerinde kalibre edilen uçla karşılaştırıldı. |
| Tipografi ve marka paleti | PASS | Modern modda sans-serif, kelime sarma, satır ve harf aralığı, renk seçimi ve bağımsız giriş efekti. |
| Geometri ve SVG | PASS | Test SVG’sinde dönüşümlü gruplar, yedi şekil türü, dolgu ve delik sınandı. |
| Robot TRACE ve FULL | PARTIAL | İç ve dış çizgiler ile ilişkili renk bölgeleri görünüyor. Tespit edilen tüm raster kenarlar kalemle çizilmiyor. |
| Rover TRACE ve FULL | PARTIAL | Tekerlekler, gövde ve sensörler işleniyor. İnce çizgilerin ve mekanik dokuların bir bölümü yalnızca renkli kaynakla tamamlanıyor. |
| SVG FULL | PASS | Test SVG’sinin yerel renk bölgeleri vuruşlarla birlikte ilerliyor. Son raster, kaynakla aynı. |
| PNG/SVG son piksel eşliği | PASS | Tamamlanan sahne, bağımsız kaynak görüntüsüyle aynı tarayıcı rasterında karşılaştırıldı. |
| Önceki üç hareket ve kapsamlı efektler | PASS | Önceki tarayıcı doğrulama betikleri güncel motorla çalıştırıldı. |
| Tüm alfabelerde el yazısı, SVG filtre ve metin öğelerinin vuruş çıkarımı | NOT TESTED | El yazısı verisi Latin A–Z ve a–z ile seçili noktalama işaretlerini kapsar. Test SVG’si temel şekillerle sınırlıdır. |
| 25 dakika render | NOT TESTED | Bu görev 118 saniyelik görsel teste odaklandı. |

Görsel doğallık öznel bir değerlendirmedir. Verilen örnek görüntüler, otomatik koordinat ve piksel ölçümlerini tamamlar.

## Yeniden kullanım

- `studio/src/theme.json` marka paletinin kaynağıdır. Yeni timeline’larda `theme: "brand"` marka varsayılanlarını etkinleştirir. Beyaz ve krem arka plan ile öğe bazlı renkler ayrı seçilebilir. Eski timeline’lar önceki varsayılanları kullanır.
- `engine.handwriting.handwriting` metni boyut, iz genişliği, harf/kelime boşluğu, satır yüksekliği ve maksimum genişlikle merkez vuruşlarına dönüştürür. Bu depoda yazılan vuruşlar depo MIT lisansıyla dağıtılır.
- `engine.stroke_plan.schedule` vuruş ve kalem kaldırma aralıklarını aynı zaman tabanına yerleştirir. `pen_window` kalem yolculuğu için giriş ve çıkış sınırı üretir.
- `engine.illustration.analyze` ve `compile_illustration` PNG kenarlarını veya SVG’nin dönüştürülmüş geometrisini işler. `trace` vuruş planı, `full` vuruş planı ile ayrı bölgesel renk zamanlaması üretir. Önceki `reveal` tarama maskesi ayrı kalır.
- Demo üretimi `CHROME_PATH=/usr/bin/chromium python scripts/build-professional-demo.py` ile yapılır. Python gereksinimlerini ve `studio` Node bağımlılıklarını önce yükleyin.
