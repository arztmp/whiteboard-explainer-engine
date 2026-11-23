"""Build the animation test timeline and a synthetic audio fixture from the four supplied PNGs."""
import copy
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import feature, measure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.trace_map import order_skeleton

PUBLIC = ROOT / "studio/public"
OUT = PUBLIC / "full-animation-demo"
INK = "#1A3748"
TEAL = "#087568"
scenes = []


def vec(x, y):
    return {"x": x, "y": y}


def text(id_, value, x, y, size=30, color=INK):
    return dict(id=id_, type="text", text=value, x=x, y=y, size=size, color=color,
                weight=700, enter="none", hand=False)


def image(id_, name, x, y, width, **properties):
    return dict(id=id_, type="image", src=f"{name}.png", x=x, y=y, w=width,
                **({"enter": "none"} | properties))


def rect(id_, x, y, w, h, fill, **properties):
    return dict(id=id_, type="rect", x=x, y=y, w=w, h=h, fill=fill, enter="none", **properties)


def add(id_, title, elements, *, pen=False, background="#F8F8EF"):
    start = 10 * len(scenes)
    scene = dict(id=id_, start=start, end=start + 10, background=background,
                 transitionIn=dict(type="push-left", duration=.8), elements=[
                     text(f"{id_}-kicker", "WHITEBOARD MOTORU  /  ANİMASYON TESTİ", 960, 83, 21, TEAL),
                     text(f"{id_}-title", title, 960, 165, 56),
                     rect(f"{id_}-rule", 960, 245, 1540, 2, "#CCDAD4"),
                     *elements,
                 ])
    if pen:
        scene["penTravel"] = dict(start=start + .15, end=start + 9.08,
                                  **{"from": vec(1040, 1270), "to": vec(1040, 1270)})
    scenes.append(scene)
    return scene


def paths(prefix, lines, first, last, color=INK, width=6, gap=.10):
    lengths = [sum(math.dist(a, b) for a, b in zip(line, line[1:])) for line in lines]
    usable = last - first - gap * (len(lines) - 1)
    start = first
    result = []
    for i, (line, length) in enumerate(zip(lines, lengths)):
        duration = usable * length / sum(lengths)
        d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in line)
        result.append(dict(id=f"{prefix}-{i}", type="path", d=d, stroke=color, strokeWidth=width,
                           hand=True, enter="draw", enterAt=round(start, 6), enterDuration=round(duration, 6)))
        start += duration + gap
    return result


def extract_trace(name, center, display_width):
    """Find alpha boundaries and visible raster edges, then retain the longest ordered pen strokes."""
    with Image.open(OUT / f"{name}.png") as source:
        rgba = source.convert("RGBA")
        rgba.thumbnail((310, 310))
        composite = Image.new("RGBA", rgba.size, "white")
        composite.alpha_composite(rgba)
        gray = np.asarray(composite.convert("L")) / 255
        alpha = np.asarray(rgba.getchannel("A")) >= 128
    visible_edge = feature.canny(gray, sigma=1.15, low_threshold=.08, high_threshold=.19)
    boundary = alpha & ~ndimage.binary_erosion(alpha)
    edges = (visible_edge & ndimage.binary_erosion(alpha)) | boundary
    candidates = order_skeleton(edges)
    chosen = sorted(candidates, key=len, reverse=True)[:24]
    chosen = [path for path in chosen if len(path) >= 10]
    ratio = display_width / rgba.width
    x0 = center[0] - rgba.width * ratio / 2
    y0 = center[1] - rgba.height * ratio / 2
    lines = []
    last = (0, 0)
    while chosen:
        _, index, reverse = min((math.dist(last, stroke[side]), i, side == -1)
                                for i, stroke in enumerate(chosen) for side in (0, -1))
        stroke = chosen.pop(index)
        if reverse:
            stroke.reverse()
        last = stroke[-1]
        sampled = stroke[::2]
        if sampled[-1] != last:
            sampled.append(last)
        lines.append([(x0 + x * ratio, y0 + y * ratio) for y, x in sampled])
    return lines, dict(strokes=len(lines), candidates=len(candidates),
                       retainedEdgeSamples=sum(len(line) for line in lines), sourceEdgePixels=int(edges.sum()))


def silhouette(name, size, count=192):
    """Sample the largest external alpha contour by arc length and align both at top center."""
    with Image.open(OUT / f"{name}.png") as source:
        alpha = source.convert("RGBA").getchannel("A")
        alpha.thumbnail((600, 600))
        mask = np.asarray(alpha) >= 128
    labels, _ = ndimage.label(mask)
    areas = np.bincount(labels.ravel())
    areas[0] = 0
    component = labels == areas.argmax()
    ring = max(measure.find_contours(np.pad(component, 1), .5), key=len) - 1
    ring = ring[:-1, ::-1]
    lo = ring.min(axis=0)
    hi = ring.max(axis=0)
    center = (lo + hi) / 2
    target = np.array([center[0], lo[1]])
    start = np.linalg.norm(ring - target, axis=1).argmin()
    ring = np.roll(ring, -start, axis=0)
    ring = np.vstack([ring, ring[0]])
    length = np.r_[0, np.cumsum(np.linalg.norm(np.diff(ring, axis=0), axis=1))]
    samples = np.linspace(0, length[-1], count, endpoint=False)
    factor = min(size[0] / (hi[0] - lo[0]), size[1] / (hi[1] - lo[1]))
    return [vec(round(x, 3), round(y, 3)) for x, y in zip(
        (np.interp(samples, length, ring[:, 0]) - center[0]) * factor,
        (np.interp(samples, length, ring[:, 1]) - center[1]) * factor)]


base = json.loads((PUBLIC / "hand-motion-demo/timeline.json").read_text())
letters = [copy.deepcopy(el) for el in base["scenes"][0]["elements"] if el["id"].startswith("ink-")]
for el in letters:
    el["enterAt"] = round(el["enterAt"] * .81, 6)
    el["enterDuration"] = round(el["enterDuration"] * .81, 6)
    el["stroke"] = "#19394B"
    el["strokeWidth"] = 8
# A shorter sentence uses a narrower pen stroke and a smaller glyph scale.
sentence = [[(0, 0), (0, 42)], [(35, 0), (35, 42), (60, 42)], [(67, 0), (67, 42)],
            [(76, 0), (92, 42), (108, 0)], [(139, 0), (117, 0), (117, 42), (139, 42)],
            [(117, 21), (136, 21)], [(151, 39), (152, 42)]]
add("writing", "Harfler, kelimeler ve cümle", letters + paths(
    "ink-line", [[(840 + x * 1.4, 700 + y * 1.4) for x, y in line] for line in sentence],
    7.05, 8.52, TEAL, 4, .055), pen=True)

house = [copy.deepcopy(el) for el in base["scenes"][1]["elements"] if el["id"].startswith("ink-")]
for el in house:
    el["x"] = 300
    el["y"] = -40
    el["enterAt"] = round(13.72 + (el["enterAt"] - 11.10) * .69, 6)
    el["enterDuration"] = round(el["enterDuration"] * .69, 6)
    el["strokeWidth"] = 6
shapes = [[(380, 570), (485, 385), (590, 570), (380, 570)],
          [(385, 645), (575, 645), (575, 815), (385, 815), (385, 645)]]
circle = [(865 + math.cos(i * math.tau / 40) * 94, 591 + math.sin(i * math.tau / 40) * 94) for i in range(41)]
add("geometry", "Geometrik şekiller ve SVG", paths("ink-shape", [*shapes, circle], 10.85, 13.55, TEAL, 6) + house,
    pen=True, background="#F0F6F5")

trace_stats = {}
for name, title in [("robot", "Robot"), ("rover", "Rover")]:
    start = len(scenes) * 10
    lines, trace_stats[name] = extract_trace(name, (960, 601), 662 if name == "robot" else 875)
    add(f"{name}-trace", f"{title}  /  TRACE",
        paths(f"ink-{name}", lines, start + .95, start + 8.42, INK, 3.3, .075) +
        [text(f"{name}-edge-note", "PNG’den çıkarılan seçili kenar çizgileri", 960, 976, 25, TEAL)], pen=True)

for name, title in [("robot", "Robot"), ("rover", "Rover")]:
    start = len(scenes) * 10
    add(f"{name}-reveal", f"{title}  /  REVEAL", [
        image(f"reveal-{name}", name, 960, 625, 635 if name == "robot" else 825,
              enter="draw", enterAt=start + .92, enterDuration=7.25, hand=True,
              reveal={"rows": 7 if name == "robot" else 6})
    ], pen=True, background="#F0F6F5")

entrances = []
for i, kind in enumerate(("draw", "slide", "rotate", "grow", "fade")):
    x = 310 + i * 325
    entrances.append(text(f"entrance-{kind}-label", kind.upper(), x, 335, 28, TEAL))
    for j, name in enumerate(("robot", "rover")):
        settings = dict(enter=kind, enterAt=60.8 + 1.38 * i + .28 * j, enterDuration=1.65, hand=False)
        if kind == "draw":
            settings["reveal"] = {"rows": 4}
        if kind == "slide":
            settings["enterOffset"] = vec(-120 if j == 0 else 155, 110 if j == 0 else -95)
        if kind == "rotate":
            settings["enterAngle"] = -175 if j == 0 else 210
        if kind == "grow":
            settings["enterScale"] = .12
        entrances.append(image(f"enter-{kind}-{name}", name, x, 540 + j * 288, 225 if j == 0 else 265, **settings))
add("entrances", "Beş giriş animasyonu", entrances)

add("opacity", "Fade in ve fade out", [
    image("fade-robot", "robot", 685, 633, 565, enter="fade", enterAt=71, enterDuration=2.4,
          enterCurve="linear", exit="fade", exitAt=75.8, exitDuration=2.3, exitCurve="ease-in"),
    image("fade-rover", "rover", 1240, 668, 690, enter="fade", enterAt=71.6, enterDuration=2.1,
          enterCurve="ease-out", exit="fade", exitAt=76.4, exitDuration=2.1, exitCurve="linear"),
], background="#F0F6F5")
add("morph", "Robot → Rover  /  Siluet dönüşümü", [
    image("morph-robot-ref", "robot", 389, 650, 346),
    image("morph-rover-ref", "rover", 1510, 657, 373),
    dict(id="morph-silhouette", type="morph", x=960, y=636, enter="none", at=81.65, duration=6.1,
         from_=silhouette("robot", (570, 500)), to=silhouette("rover", (570, 500)), fill="#267780"),
    text("morph-note", "Eşleştirilmiş dış kontur noktaları", 960, 978, 27, TEAL),
])
scenes[-1]["elements"][-2]["from"] = scenes[-1]["elements"][-2].pop("from_")
add("zoom", "Zoom in ve zoom out", [
    image("zoom-rover", "rover", 960, 646, 705,
          zoom={"at": 91.1, "in": 2.3, "hold": 1.4, "out": 2.85, "scale": 1.48, "origin": vec(-80, -60)}),
], background="#F0F6F5")
add("scatter", "Pixel scatter  /  Dağılma ve birleşme", [
    image("scatter-rover", "rover", 960, 632, 780, scatter=dict(
        at=101.3, out=2.25, hold=1.35, back=2.55, columns=14, rows=10,
        direction=vec(-128, -110), returnDirection=vec(115, -73))),
])

obj = copy.deepcopy(next(el for el in base["scenes"][2]["elements"] if el["id"] == "drag-object"))
obj["id"] = "drag-robot"
obj["carry"].update(start=111.8, contact=113, pickup=113.25, land=116.65, release=116.95, end=118.8)
obj["carry"]["grip"] = vec(36, -44)
obj["carry"]["target"] = vec(1440, 675)
obj["carry"]["from"] = vec(1040, 1270)
obj["carry"]["to"] = vec(1040, 1270)
add("drag", "Yüzey üzerinde sürükleme", [
    rect("drag-track", 955, 753, 1040, 7, "#C2D7CC"),
    rect("drag-destination", 1440, 675, 280, 216, "#DBEBDE", radius=22),
    image("drag-robot", "robot", 460, 675, 272, carry=obj["carry"]),
    text("drag-origin", "BAŞLANGIÇ", 460, 877, 26, TEAL),
    text("drag-target", "HEDEF", 1440, 877, 26, TEAL),
], background="#F0F6F5")
add("multiple", "Birlikte hareket ve katman sırası", [
    image("move-rover", "rover", 465, 646, 610, z=1, moves=[
        dict(at=121, duration=2.5, x=910, y=650), dict(at=123.5, duration=1.5, scale=1.16, rotate=-11),
        dict(at=125, duration=1.7, scale=.76, rotate=8, opacity=.55),
        dict(at=126.7, duration=1.3, x=1455, rotate=0, opacity=1)]),
    image("move-robot", "robot", 1430, 626, 556, z=2, moves=[
        dict(at=121, duration=2.45, x=920, y=630), dict(at=124, duration=2.5, rotate=18, scale=.85),
        dict(at=126.5, duration=2.35, x=-330, opacity=.9)]),
])
add("slide-left", "Sağdan sola sahne geçişi", [
    rect("slide-left-board", 960, 633, 1410, 522, "#DFEFE9", radius=30),
    image("slide-robot", "robot", 745, 640, 495),
    image("slide-rover", "rover", 1210, 640, 575),
], background="#EAF4F1")

words = [dict(text=word, start=at, end=round(at + .40, 2))
         for word, at in zip(("ROBOT", "ROVER", "HAREKET", "SES", "ZAMAN"), (141.2, 142.55, 144.1, 145.4, 146.85))]
add("sync", "Ses ve kelime zaman damgaları", [
    image("sync-robot", "robot", 750, 593, 395),
    image("sync-rover", "rover", 1160, 616, 510),
    dict(id="sync-words", type="caption", x=960, y=895, maxWidth=1300, size=43,
         words=words, activeColor="#A9F4DA", bg="#193C47", activeScale=1.08, enter="none"),
    text("sync-note", "Sentetik ses  /  Her vurgu bir zaman damgasına bağlı", 960, 980, 25, TEAL),
])
for scene in scenes:
    if scene["id"] in {"geometry", "rover-trace", "robot-reveal"}:
        scene["penTravel"]["scale"] = {"geometry": .84, "rover-trace": 1.12, "robot-reveal": .94}[scene["id"]]

rate = 48000
t = np.arange(round(.24 * rate)) / rate
pcm = (np.sin(2 * math.pi * 750 * t) * np.minimum(1, t * 160) *
       np.minimum(1, (.24 - t) * 160) * 19000).astype("<i2")
with wave.open(str(OUT / "timing-tone.wav"), "wb") as output:
    output.setparams((1, 2, rate, len(pcm), "NONE", "not compressed"))
    output.writeframes(pcm.tobytes())
timeline = dict(style="A", fps=30, width=1920, height=1080, duration=150, font="sans",
                sceneSlideLeft=True, hand=base["hand"], carryHand=base["carryHand"], scenes=scenes,
                sfx=[dict(src="timing-tone.wav", at=word["start"], volume=.66) for word in words])
(OUT / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n")
(OUT / "timing.json").write_text(json.dumps(dict(words=words, trace=trace_stats), ensure_ascii=False, indent=2) + "\n")

if "--endurance" in sys.argv:
    absolute_times = {"at", "start", "end", "enterAt", "exitAt", "contact", "pickup", "land", "release"}

    def shift(value, offset):
        if isinstance(value, list):
            return [shift(item, offset) for item in value]
        if isinstance(value, dict):
            return {key: round(item + offset, 6) if key in absolute_times else shift(item, offset)
                    for key, item in value.items()}
        return value

    long_scenes = []
    for index in range(108):
        cycle, source_index = divmod(index, len(scenes))
        scene = shift(scenes[source_index], cycle * 150)
        scene["id"] = f"{cycle}-{scene['id']}"
        for el in scene["elements"]:
            el["id"] = f"{cycle}-{el['id']}"
        long_scenes.append(scene)
    long_audio = [shift(cue, cycle * 150) for cycle in range(7) for cue in timeline["sfx"]]
    (OUT / "endurance.json").write_text(json.dumps(
        timeline | {"fps": 2, "duration": 1080, "scenes": long_scenes, "sfx": long_audio},
        ensure_ascii=False, separators=(",", ":")) + "\n")
