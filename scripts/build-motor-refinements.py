"""Compile the targeted correction film and retain the original acceptance fixture for regression."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.background import background_push
from engine.handwriting import handwriting
from engine.scientific import formula_strokes
from engine.stroke_plan import THEME, pen_window, schedule

PUBLIC = ROOT / "studio/public"
OUT = PUBLIC / "motor-demo"
legacy = json.loads((OUT/"timeline.json").read_text())
legacy_report = json.loads((OUT/"report.json").read_text())
sources = {item["file"][:3]: item["file"] for item in legacy_report["assets"]}
navy, white, cream, orange = (THEME[k] for k in ("navy", "white", "cream", "orange"))
dark_ink_shadow = "0px 2px 2px rgba(15,16,29,.88)"
light_ink_shadow = "0px 1px 2px rgba(255,240,210,.9)"
scenes, equations = [], []
clock = 0


def point(x, y):
    return dict(x=x, y=y)


def text(id_, label, x, y, size, color=navy, **options):
    return dict(id=id_, type="text", text=label, x=x, y=y, size=size, color=color,
                mode="typography", enter="none", **options)


def add(id_, title, duration, elements, *, pen=None, camera=None, heading=None):
    global clock
    title_ink = text(f"{id_}-title", title, 960, 92, 48, screenFixed=True, weight=800) if title else None
    if title_ink and heading:
        title_ink.update(heading)
    scene = dict(id=id_, start=clock, end=clock+duration, background=white,
                 transitionIn=dict(type="push-left", duration=.65),
                 elements=([title_ink] if title_ink else []) + elements)
    if pen is not None:
        scene["penTravel"] = pen_window(clock+pen, clock+duration-1.05, scale=.68)
    if camera:
        scene["camera"] = camera
    scenes.append(scene)
    clock += duration


def formula(id_, label, expr, x, y, size, start, end, color=navy, shadow=None):
    prefix = "ink-" + id_
    strokes = schedule(formula_strokes(expr, x, y, size, color=color, width=5.4),
                       clock+start, clock+end, prefix)
    if shadow:
        for stroke in strokes:
            stroke["inkShadow"] = shadow
    equations.append(dict(id=id_, label=label, start=clock+start, end=clock+end,
                          strokes=[stroke["id"] for stroke in strokes]))
    return strokes


row = lambda *items: ("row", *items)
power = lambda symbol: ("sup", symbol, "2")
sub = lambda symbol, subscript: ("sub", symbol, subscript)
fraction = lambda numerator, denominator: ("fraction", numerator, denominator)
gravity = row("F", "=", "G", fraction(row(sub("m", "1"), sub("m", "2")), power("r")))
squares = row(power("a"), "+", power("b"))
sprite = PUBLIC/"hand-motion-demo/El.png"


def push(id_, source):
    return background_push(id_, sources[source], sprite, legacy["carryHand"]["tip"],
                           clock+.14, clock+4.5, clock+5.35)


bg, alpha = push("landscape-a", "S20")
note, _ = handwriting("Gravity shapes worlds.", 245, 279, 65, color=white, width=5)
note_elements = schedule(note, 6.4, 12.6, "ink-landscape-note")
for stroke in note_elements:
    stroke["inkShadow"] = dark_ink_shadow
add("background-one", "Gravity on the whiteboard", 22, [
    bg,
    text("landscape-subtitle", "Mass, distance and motion", 960, 157, 33, white, inkShadow=dark_ink_shadow,
         screenFixed=True, weight=550, enterAt=5.45),
    *note_elements,
    *formula("gravity-bg", "F = Gm₁m₂/r²", gravity, 1060, 273, 93, 13.25, 19.7, white, dark_ink_shadow),
], pen=5.45, heading=dict(color=white, inkShadow=dark_ink_shadow, enterAt=5.45))

bg, _ = push("landscape-b", "S02")
add("background-two", "A second landscape", 11, [
    bg,
    text("bright-text", "Motion across the surface", 970, 860, 49, navy, inkShadow=light_ink_shadow,
         enterAt=clock+5.45, screenFixed=True, weight=800)
], heading=dict(color=white, inkShadow=dark_ink_shadow, enterAt=clock+5.45))

add("basic-pen", "Arithmetic in pen strokes", 25, [
    *formula("add", "2 + 3 = 5", "2 + 3 = 5", 365, 421, 100, 1, 6.2),
    *formula("subtract", "8 − 3 = 5", "8 − 3 = 5", 1125, 421, 100, 6.8, 12),
    *formula("multiply", "2 × 4 = 8", "2 × 4 = 8", 365, 741, 100, 12.6, 17.8),
    *formula("divide", "8 ÷ 2 = 4", "8 ÷ 2 = 4", 1125, 741, 100, 18.4, 23.6),
], pen=.1)

add("science-pen", "Scientific notation in pen strokes", 25, [
    *formula("einstein", "E = mc²", row("E", "=", "m", power("c")), 400, 386, 120, 1, 7),
    *formula("newton", "F = ma", row("F", "=", "ma"), 1100, 386, 120, 7.65, 13.2),
    *formula("gravity", "F = Gm₁m₂/r²", gravity, 620, 755, 125, 14, 23),
], pen=.1)

add("advanced-pen", "Powers, radicals and fractions", 33, [
    *formula("pythagoras", "a² + b² = c²", row(squares, "=", power("c")), 260, 413, 113, 1, 8.1),
    *formula("radical", "x = √(a² + b²)", row("x", "=", ("root", squares)), 1020, 413, 113, 8.8, 17.1),
    *formula("velocity", "v = Δx/Δt", row("v", "=", fraction("Δx", "Δt")), 395, 802, 104, 17.8, 24),
    *formula("omega", "ω = 2π/T", row("ω", "=", fraction("2π", "T")), 1110, 802, 104, 24.7, 31.55),
], pen=.1)

add("operators-pen", "Summation and integration limits", 21, [
    *formula("sum", "∑ᵢ₌₁ⁿ mᵢ", row(("limits", "i=1", "n"), sub("m", "i")), 485, 546, 139, 1.1, 9.3),
    *formula("integral", "∫₀¹ x² dx = 1/3", row(("integral", "0", "1"), power("x"), "dx", "=", fraction("1", "3")),
             1030, 546, 122, 10, 19.5),
], pen=.1)

add("zoom-refined", "Object and camera zoom", 12, [
    dict(id="zoom-clock", type="image", src=sources["S29"], x=490, y=500, w=435, enter="none",
         zoom=dict(at=clock+1, hold=.6, out=1.4, scale=1.32, origin=point(-38, 16), **{"in":1.4})),
    dict(id="zoom-webb", type="image", src=sources["S11"], x=1320, y=485, w=510, enter="none"),
    text("zoom-clock-caption", "Clock mechanism", 480, 981, 30, screenFixed=True),
    text("zoom-webb-caption", "Webb telescope", 1440, 981, 30, screenFixed=True),
], camera=[dict(at=clock+t, x=x, y=y, scale=s) for t,x,y,s in [
    (0,960,540,1), (5,960,540,1), (7,1075,528,1.24), (8,1075,528,1.24), (10.5,960,540,1)]])

time_fields = {"enterAt", "exitAt", "start", "end", "at", "contact", "pickup", "land", "release"}


def shift_times(value, delta):
    if isinstance(value, list):
        return [shift_times(item, delta) for item in value]
    if not isinstance(value, dict):
        return value
    return {key: round(item+delta, 6) if key in time_fields and isinstance(item, (int, float))
            else shift_times(item, delta) for key, item in value.items()}


# These fixtures retain their original drawing and effect timings.
for id_ in ("reveal", "full-one", "svg", "draw", "slide", "rotate", "grow", "fade", "reassemble", "transform"):
    original = next(scene for scene in legacy["scenes"] if scene["id"] == id_)
    scenes.append(shift_times(deepcopy(original), clock-original["start"]))
    clock = scenes[-1]["end"]

timeline = {key: value for key, value in legacy.items() if key not in {"sfx", "allowMorph", "allowLegacyBackgroundPlacement"}}
timeline.update(scenes=scenes, duration=clock)
report = dict(duration=clock, handAlpha=alpha, handHeight=300, backgroundInset=150, formulas=equations,
              scenes=[{key: scene[key] for key in ("id", "start", "end")} for scene in scenes],
              effectsDisabled=["MORPH", "Raster PNG TRACE"])
(OUT/"refinements.json").write_text(json.dumps(timeline, ensure_ascii=False, separators=(",", ":"))+"\n")
(OUT/"refinements-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
