# Whiteboard animasyon testi

| Özellik | Durum | Doğrulama |
|---|---|---|
| Harf, kelime ve cümle yazma | PASS | Kalem, sırayla açılan SVG vuruşlarının ucunu takip eder. İki boyut ve iki renk vardır. |
| Geometrik şekil ve SVG çizme | PASS | Üçgen, dörtgen, daire ve ev yolları kademeli çizilir. |
| Robot TRACE | PARTIAL | Seçili raster kenarlar çizilir. İnce ayrıntılar ve renkler yeniden üretilmez. |
| Rover TRACE | PARTIAL | Seçili raster kenarlar çizilir. Karmaşık tekerlek ve gövde ayrıntılarının bir kısmı kaybolur. |
| Robot ve rover REVEAL | PASS | Kalemin izlediği maske orijinal renkli PNG’yi kademeli açar. |
| DRAW, SLIDE, ROTATE, GROW ve FADE | PASS | Her giriş robot ve rover üzerinde gösterilir. DRAW raster görsellerde kalemsiz çizim maskesini kullanır. |
| FADE IN ve FADE OUT | PASS | İki görselde bağımsız süre ve eğriler kullanılır. |
| Robot → Rover MORPH | PARTIAL | Eşleştirilmiş 192 dış kontur noktası şekli dönüştürür. İç çizgiler, delikler ve renk dokuları dönüşmez. |
| ZOOM IN ve ZOOM OUT | PASS | Ayarlanmış odak noktası sabit kalır, görselin en boy oranı korunur. |
| PIXEL SCATTER | PASS | 140 ızgara parçası dağılır ve birleşir. Birleşme sonunda tarayıcı kareleri piksel düzeyinde başlangıçla aynıdır. |
| Sürükleme | PASS | Açık elin işaret parmağı nesneyle aynı temas noktasını izler. Nesne yüksekliği sabit kalır. |
| Nesne hareketi ve katman sırası | PASS | Eşzamanlı hareket, ölçek, açı, opaklık, katman, hedef konum ve kadrajdan çıkış kontrol edilir. |
| Giriş, çıkış ve el çakışması | PASS | Kalemli ve açık el sahnelerinde tek el katmanı bulunur. El sahne geçişlerinde görünmez. |
| SceneSlideLeft | PASS | 14 geçişin 336 karesinde iki kırpılmış sahne grubu boşluksuz hareket eder. |
| Ses ve kelime zaman damgaları | PASS | Sentetik ses vurguları ve görsel kelime zamanlaması kodlanmış MP4’te karşılaştırılır. |
| Gerçek seslendirme senkronizasyonu | NOT TESTED | Gönderilen dosyalar arasında gerçek seslendirme ve kelime hizalaması yoktu. |
| Önceki üç hareketin regresyonu | PASS | Önceki test videosunun 900 karesi güncel motorla yeniden kontrol edilir. |
| 18 dakika render dayanıklılığı | PASS | 108 sahne, 640×360 ve 2 FPS uzun süre testi. |
| 15–20 dakika 1080p30 render dayanıklılığı | NOT TESTED | 150 saniyelik tam çözünürlük testi ile düşük çözünürlüklü uzun süre testi ayrı kapsamları ölçer. |

`coordinates.csv` temas noktalarını, `browser-checks.json` tarayıcı doğrulamasını, `timing-report.json` kodlanmış MP4 ölçümlerini içerir. `endurance-report.json` uzun render verilerini ve zaman quantizasyonunu, `assets.json` orijinal dosyaların özetlerini içerir.
