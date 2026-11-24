"""Compile the writing and illustration fixtures using the public stroke planners."""
import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.handwriting import handwriting
from engine.illustration import analyze, compile_illustration
from engine.stroke_plan import THEME, pen_window, schedule

PUBLIC = ROOT / "studio/public"
OUT = PUBLIC / "professional-draw"
old = json.loads((PUBLIC / "hand-motion-demo/timeline.json").read_text())
chrome = os.environ.get("CHROME_PATH", "chromium")
palette = THEME
scenes = []
layouts = {}
coverage = []
reproduce = {}
clock = 0


def typography(id_, value, x, y, size=29, *, color=None, **props):
    return dict(id=id_, mode="typography", type="text", text=value, x=x, y=y, size=size,
                **({"font": "sans", "weight": 600, "letterSpacing": .3, "color": color or palette["navy"],
                    "enter": "none"} | props))


def image(id_, src, x, y, w, **props):
    return dict(id=id_, type="image", src=src, x=x, y=y, w=w, **({"enter": "none"} | props))


def add(id_, title, duration, content, *, pen=False, scale=.76, white=False):
    global clock
    items = list(content)
    items[:0] = [typography(f"{id_}-title", title, 960, 135, 56),
                 dict(id=f"{id_}-rule", type="rect", x=960, y=216, w=1440, h=3,
                      fill=palette["orange"], stroke="none", enter="none")]
    scene = dict(id=id_, start=clock, end=clock+duration, background=palette["white" if white else "cream"],
                 elements=items, transitionIn=dict(type="push-left", duration=.72))
    if pen:
        scene["penTravel"] = pen_window(clock+.10, clock+duration-.9, scale=scale)
    scenes.append(scene)
    clock += duration


def write(text, id_, x, y, size, first, last, **options):
    strokes, layout = handwriting(text, x, y, size, **options)
    layouts[id_] = layout
    return schedule(strokes, clock+first, clock+last, "ink-" + id_)


legacy = []
for el in old["scenes"][0]["elements"]:
    if el["type"] != "path":
        continue
    legacy.append(dict(el, id=f"legacy-{el['id']}", enter="none", enterAt=0, hand=False, stroke=palette["navy"],
                       d=re.sub(r"(\d+) (\d+)", lambda m: f"{320+int(m[1])*.66:.2f} {-6+int(m[2])*.66:.2f}", el["d"])))
add("comparison", "Aynı metin, iki yazım biçimi", 9, [
    typography("legacy-label", "ÖNCEKİ ÇİZGİ HARFLER", 970, 248, 22),
    *legacy, typography("new-label", "YENİ MERKEZ VURUŞLARI", 970, 575, 22),
    *write("HELLO WORLD", "headline", 435, 810, 140, .85, 7.28, width=6.4, tracking=7, word_gap=41),
], pen=True, white=True)
add("sentence", "Kalemle cümle yazımı", 13, write(
    "Imagine a world without gravity.", "sentence", 240, 640, 86, 1, 11.45,
    width=4.5, max_width=1490, tracking=5, word_gap=33), pen=True)
add("multiline", "Satır düzeni ve harf aralıkları", 12, [
    *write("Science explains the impossible.", "multiline", 310, 485, 105, .80, 10.20,
           width=5, max_width=1050, line_height=1.56, tracking=7, word_gap=41),
    typography("typography-sample", "Tipografi modu, ayrı bir metin katmanı olarak kontrollü satır aralığı ve otomatik satır kaydırma kullanır.",
               960, 872, 28, maxWidth=750, lineHeight=1.55, letterSpacing=.5, enter="fade", enterAt=clock+10.1),
], pen=True, white=True)

svg = analyze(OUT / "geometry.svg", chrome)
shapes, stats = compile_illustration(svg, "geometry.svg", "ink-geometry", (960, 590), 1320, clock+.70, clock+6.69, mode="trace")
for el in shapes:
    el["strokeWidth"] = 3.6
coverage.append(stats)
add("geometry", "Geometrik çizim ve SVG yolları", 8, shapes, pen=True, scale=.74)

for name, figure, width in [("robot", "Robot", 676), ("rover", "Rover", 1045)]:
    raster = analyze(PUBLIC / "full-animation-demo" / (name + ".png"), chrome)
    for mode, duration, maximum in (("trace", 11, 43), ("full", 13, 52)):
        prefix = f"ink-{name}-{mode}"
        duration += (1 if mode == "trace" else 0) if name == "robot" else 3
        el, stats = compile_illustration(raster, f"/full-animation-demo/{name}.png", prefix,
                                        (960, 595), width, clock+.73, clock+duration-1.58,
                                        mode=mode, limit=maximum, allow_trace=True)
        coverage.append(stats)
        if mode == "full":
            reproduce[name] = copy.deepcopy(el[0])
        add(name+"-"+mode, figure+" · "+("Dış ve iç çizgiler" if mode=="trace" else "Çizgiler ve bölgesel renk"),
            duration, el, pen=True, scale=.68, white=mode=="full")

detail, stats = compile_illustration(svg, "geometry.svg", "ink-detail", (950, 557), 1470, clock+.88, clock+5.72, mode="full")
coverage.append(stats)
reproduce["svg"] = copy.deepcopy(detail[0])
add("close-up", "Yakın plan · Kalemin temas ve kalkış anları", 7, detail, pen=True, scale=.97)

compare = []
for name, middle, width, y, offset in (("robot", 490, 300, 504, 150), ("rover", 1420, 382, 504, 208),
                                        ("svg", 960, 224, 885, 165)):
    original = reproduce[name]
    panel = dict(original, id=f"finished-{name}", x=middle-offset, y=y, w=width,
                 h=original["h"]*width/original["w"], enterAt=clock)
    compare.extend([panel, image(f"original-{name}", original["src"], middle+offset, y, width, h=panel["h"]),
                    typography(f"pair-{name}", f"{name.upper()}  ·  TAMAMLANAN / ORİJİNAL", middle,
                               287 if name != "svg" else 764, 23)])
add("pixel-check", "Tamamlanan görsel ve orijinal", 6, compare, white=True)

carry = copy.deepcopy(next(e["carry"] for e in old["scenes"][2]["elements"] if e.get("carry")))
carry.update(start=clock+.45, contact=clock+1.60, pickup=clock+1.84, land=clock+4.4,
             release=clock+4.66, end=clock+6.90,
             target={"x": 1400, "y": 705}, grip={"x": 16, "y": -20})
add("regression", "Regresyon · Sürükleme, kayma ve büyüme", 8, [
    dict(id="ground", type="rect", x=960, y=767, w=1200, h=4, fill=palette["gray"], enter="none"),
    image("regression-drag", "/full-animation-demo/robot.png", 480, 705, 205, carry=carry),
    image("regression-grow", "/full-animation-demo/rover.png", 970, 445, 350, enter="grow",
          enterAt=clock+1.1, enterDuration=.9, moves=[dict(at=clock+3.4, duration=1.8, x=1320, rotate=8)]),
], white=True)

timeline = dict(style="B", width=1920, height=1080, fps=30, duration=clock, font="sans", theme="brand",
                sceneSlideLeft=True, scenes=scenes,
                hand=dict(old["hand"], src="/hand-motion-demo/Kalem_El.png"),
                carryHand=dict(old["carryHand"], src="/hand-motion-demo/El.png"))
(OUT / "timeline.json").write_text(json.dumps(timeline, separators=(",", ":"), ensure_ascii=False) + "\n")
(OUT / "analysis.json").write_text(json.dumps({"coverage": coverage, "handwriting": layouts,
                                           "scenes": [{"id": s["id"],"start": s["start"],"end": s["end"]}
                                                      for s in scenes]}, ensure_ascii=False, indent=2) + "\n")
