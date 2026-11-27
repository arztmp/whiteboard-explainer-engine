# Motor yazı ve formül testi

`studio/public/font-writing-test/Motor_Test.json` beyaz zeminli, 1920×1080 ve
30 FPS bir test planıdır. Yazı ağırlığı sahne planındaki role göre seçilir.
Başlık 600, gövde 400 ağırlıktadır. Bir satır ancak plan onu içerirse ekranda
görünür. Matematiksel dizgi mevcut KaTeX yolunu kullanır.

```bash
cd studio
npm ci
npm run render -- C /kaggle/working/Motor_Font_Test.mp4 \
  '--props={"videoId":"font-writing-test","timelineFile":"Motor_Test.json"}'
```

Tarayıcı yolu gerekiyorsa `--browser-executable` ile verilir. Testin hazır
varlıkları depodadır. Aynı planı tekrar üretmek için depo kökünden
`python -m pip install -r requirements.txt` ardından
`python scripts/build-font-test.py` çalıştırın.

## Yeni sahne planları için WRITE ve FORMULA

Kaynak JSON, olağan timeline alanlarına ek olarak sahne başına isteğe bağlı
`writing` ve `formulas` alanlarını alır. Şunları ilgili sahneye ekleyin.

```json
{
  "writing": {
    "offset": 1,
    "duration": 12,
    "speed": 1.25,
    "rows": [
      {"content": "Gravity", "role": "title", "x": 960, "baseline": 290, "size": 110},
      {"content": "İğne, ölçü — Grüße!", "x": 960, "baseline": 520, "size": 82, "color": "#184c72"}
    ]
  },
  "formulas": [
    {"latex": "\\int_0^L f(x)\\,dx", "x": 960, "y": 805, "size": 95, "color": "#222b39",
     "offset": 3, "duration": 0.7}
  ]
}
```

`python scripts/compile-pen-writing.py kaynak.json studio/public/proje/timeline.json`
komutu native timeline ve yanındaki yazı SVG'lerini oluşturur. Yazı hızı
vuruşlara ayrılan süreyi böler. Konumlar sahne koordinatları, süreler
saniyedir. FORMULA, tam KaTeX dizgisini süreli geçişle gösterir. Kalemle
yazılacak matematik için WRITE satırları ayrıca `row`, `fraction`, `sup`,
`sub`, `root` ve `limits` ifade düğümlerini kabul eder. Örnek içerik
`["fraction", ["sub","m","1"], ["sup","r","2"]]`.

WRITE, Be Vietnam Pro'nun mevcut gliflerini o glife ait sıralı kalem
vuruşları boyunca açar. Font paketinde bulunmayan Yunan harfleri ve bazı
bilimsel semboller için belirli, sıralı vektör vuruşları kullanılır.
Kapsam dışındaki karakterler derlemeyi durdurur. Geçersiz LaTeX, plan
derlenirken ve Remotion metadata doğrulamasında reddedilir.

Otomatik kontroller için depo kökünden `python -m pytest -q` ve
`CHROME_PATH=/usr/bin/chromium node studio/scripts/verify-font-writing.cjs`
çalıştırın. İkinci komut seçili kareleri inceler ve MP4 üretmez.
