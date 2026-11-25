"""Build one timeline for the six path-driven drawing fixtures."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.pen_paint import compile_paint
from engine.stroke_plan import THEME, pen_window

PUBLIC = ROOT/"studio/public"
MOTOR = PUBLIC/"motor-demo"
HAND = PUBLIC/"hand-motion-demo"
OUTPUT = MOTOR
original = json.loads((HAND/"timeline.json").read_text())
chrome = os.environ.get("CHROME_PATH", "/usr/bin/chromium")


def asset(prefix):
    return next(MOTOR.glob(f"{prefix}*.png"))


scenes, reports = [], []
cur = 0.
for mode, id_, name, source, substitute in (
    ("reveal", "galaxy", "Spiral galaxy", asset("S30"), None),
    ("reveal", "clock", "Radial clock mechanism", asset("S29"), "Saturn"),
    ("draw", "butterfly", "Butterfly", asset("S17"), None),
    ("draw", "robot", "Rounded robot", PUBLIC/"full-animation-demo/robot.png", "Apple"),
    ("full", "portrait", "Isaac Newton", asset("S09"), None),
    ("full", "rover", "Mars Rover", PUBLIC/"full-animation-demo/rover.png", None),
):
    from PIL import Image
    with Image.open(source) as im:
        width = min(1270, round(im.width/im.height*790))
    src = "/" + source.relative_to(PUBLIC).as_posix()
    elements, done, report = compile_paint(source, src, mode, (960, 575), width, cur+1.1, chrome, prefix=id_)
    report.update(id=id_, name=name, substitutedFor=substitute,
                  sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  startFrame=round(cur*30), drawingStart=elements[1]["enterAt"],
                  lastContact=elements[-1]["enterAt"]+elements[-1]["enterDuration"])
    exit_frame = int(done*30+1)+19
    end_frame = exit_frame+60
    effect = {"reveal":"PNG REVEAL", "draw":"DRAW ENTRANCE", "full":"FULL ILLUSTRATION DRAW"}[mode]
    title = dict(id=f"{id_}-title", type="text", text=f"{effect} · {name}", x=960,y=88,size=46,
                 color=THEME["navy"], weight=750, enter="none",mode="typography")
    scenes.append(dict(id=id_, start=cur, end=end_frame/30, background=THEME["white"],
                       transitionIn=dict(type="none"), elements=[title,*elements],
                       penTravel=pen_window(cur+.36, exit_frame/30, scale=.68)))
    report.update(endFrame=end_frame, holdFrames=60)
    reports.append(report)
    cur=end_frame/30
    print(id_, report["strokeCount"], report["requiredSeconds"], flush=True)
timeline=dict(style="B", width=1920, height=1080, fps=30, duration=cur, font="sans",
              theme="brand", background=THEME["white"], scenes=scenes,
              hand=dict(original["hand"],src="/hand-motion-demo/Kalem_El.png"))
(OUTPUT/"draw-test.json").write_text(json.dumps(timeline, separators=(",",":"))+"\n")
(OUTPUT/"draw-report.json").write_text(json.dumps(reports, indent=2)+"\n")
