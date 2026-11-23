"""Verify the encoded fixture and compare original and final pixels before H.264 compression."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1])
video = out / "professional-draw.mp4"
browser = json.loads((out / "browser-verification.json").read_text())
analysis = json.loads((ROOT / "studio/public/professional-draw/analysis.json").read_text())


def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE).stdout


probe = json.loads(run("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(video)))["streams"][0]
actual = (probe["width"], probe["height"], probe["avg_frame_rate"], float(probe["duration"]), int(probe["nb_frames"]))
assert actual == (1920, 1080, "30/1", 118, 3540), actual
run("ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-")
comparison = {}
with Image.open(out / "original-comparison.png") as sheet:
    for name, (final, reference) in browser["pixelRects"].items():
        a, b = np.asarray(sheet.crop(final), dtype=np.int16), np.asarray(sheet.crop(reference), dtype=np.int16)
        difference = np.abs(a - b)
        count = int(np.count_nonzero(np.any(difference, axis=-1)))
        assert count == 0, (name, count)
        comparison[name] = {"comparedPixels": int(a.shape[0] * a.shape[1]), "differentPixels": count,
                            "meanAbsoluteChannelError": float(difference.mean()), "maxChannelError": int(difference.max())}
(out / "pixel-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
(out / "illustration-coverage.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n")

sample_offsets = {
    "comparison": [1.9, 4.55, 7.75],
    "sentence": [2.5, 6.55, 10.0, 11.9],
    "multiline": [2.3, 6.5, 9.65, 10.9],
    "geometry": [1.75, 3.55, 5.5, 7.0],
    "robot-trace": [2.4, 4.65, 7.5, 10.7],
    "robot-full": [1.3, 3.5, 6.8, 9.4, 11.8],
    "rover-trace": [2.4, 5.65, 10.9, 12.8],
    "rover-full": [1.3, 4.7, 8.1, 12.2, 14.8],
    "close-up": [1.0, 2.0, 3.8, 6.10],
    "pixel-check": [2.0],
    "regression": [1.9, 3.6, 5.6],
}
samples = {round((scene["start"] + offset) * 30): scene["id"]
           for scene in analysis["scenes"] for offset in sample_offsets[scene["id"]]}
for scene in analysis["scenes"][1:]:
    if scene["id"] in {"sentence", "robot-full", "regression"}:
        samples[round((scene["start"] - .35) * 30)] = "slide-left"
samples = dict(sorted(samples.items()))
frames = out / "frames"
frames.mkdir(exist_ok=True)
select = "select='" + "+".join(f"eq(n,{frame})" for frame in samples) + "'"
run("ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", select, "-fps_mode", "vfr",
    "-threads", "1", str(frames / "%02d.png"))
for i, (frame, label) in enumerate(samples.items(), 1):
    (frames / f"{i:02}.png").replace(frames / f"{frame:04}-{label}.png")
assert len(samples) >= 30

for group, selected in {
    "writing-comparison": [p for p in sorted(frames.glob("*.png")) if any(p.stem.endswith(s) for s in ["-comparison", "-sentence", "-multiline"])],
    "robot-stages": [p for p in sorted(frames.glob("*.png")) if "-robot-" in p.stem],
    "rover-stages": [p for p in sorted(frames.glob("*.png")) if "-rover-" in p.stem],
    "sample-frames": sorted(frames.glob("*.png")),
}.items():
    columns = 5 if group == "sample-frames" else 3
    rows = (len(selected) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 384, rows * 240), "#F2EDE0")
    draw = ImageDraw.Draw(sheet)
    for i, p in enumerate(selected):
        x, y = i % columns * 384, i // columns * 240
        with Image.open(p) as still:
            sheet.paste(still.resize((384, 216), Image.Resampling.LANCZOS), (x, y))
        frame, label = p.stem.split("-", 1)
        draw.text((x+10,y+222), f"{int(frame)/30:.2f} s  {label}", "#222B39")
    sheet.save(out / f"{group}.png")

elapsed, rss = Path(sys.argv[2]).read_text().split()
performance = dict(width=1920,height=1080,fps=30,frames=3540,seconds=118,
                   elapsedSeconds=float(elapsed),maxProcessRssKiB=int(rss),decodedWithoutErrors=True,
                   extractedSamples=len(samples))
(out / "performance.json").write_text(json.dumps(performance, indent=2) + "\n")
print(json.dumps({"performance":performance,"pixelComparison":comparison},ensure_ascii=False))
