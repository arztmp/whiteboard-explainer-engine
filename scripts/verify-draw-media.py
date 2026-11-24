"""Verify paint coverage in rendered browser frames, decode the MP4, and package evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

out = Path(sys.argv[1])
performance = Path(sys.argv[2])
fixtures = Path(__file__).resolve().parents[1]/"studio/public/motor-demo"
stage = sys.argv[3] if len(sys.argv) > 3 else "all"
scenes = json.loads((fixtures/"draw-report.json").read_text())
browser = json.loads((out/"browser.json").read_text())
evidence = out/"pixel-evidence"


def pixels(name):
    with Image.open(evidence/f"{name}.png") as image:
        return np.asarray(image.convert("RGB")).astype(np.int16)


for scene, result in zip(scenes, browser["scenes"], strict=True):
    delta = np.abs(pixels(scene["id"]+"-painted")-pixels(scene["id"]+"-original")).max(axis=2)
    result["finalDifferentPixels"] = int(np.count_nonzero(delta))
    result["finalMaxChannelDifference"] = int(delta.max())
    result["finalPixelExact"] = not bool(delta.any())
    assert result["finalPixelExact"], (scene["id"], result["finalDifferentPixels"], result["finalMaxChannelDifference"])
for probe in browser["probes"]:
    a, b = probe["a"], probe["b"]
    delta = np.abs(pixels(probe["key"]+"-after")-pixels(probe["key"]+"-before")).max(axis=2)
    y, x = np.where(delta > 0)
    points = np.column_stack((x, y))
    distance, _ = cKDTree(b["swept"]).query(points)
    outside = distance > b["radius"]+3
    # A few edge pixels can have low-amplitude antialiasing changes when a
    # completed segment is rasterized with a longer subpath. Account for them
    # explicitly instead of counting them as newly exposed artwork.
    maximum_outside = int(delta[y[outside], x[outside]].max(initial=0))
    assert maximum_outside <= 8, (probe["key"], maximum_outside)
    material = delta[y, x] > 8
    probe["changedPixels"] = int(material.sum())
    probe["maxDistancePx"] = round(float(distance[material].max(initial=0)),3)
    probe["outsideBrushPixels"] = int(outside.sum())
    probe["outsideBrushMaxChannelDifference"] = maximum_outside
assert all(any(p["changedPixels"] for p in browser["probes"] if p["key"].startswith(r["id"]+"-")) for r in scenes)
(out/"pixel-tests.json").write_text(json.dumps(browser,indent=2)+"\n")
print(json.dumps({"visualSamples":len(browser["probes"]), "browser":browser["scenes"]}))
if stage == "pixels":
    raise SystemExit(0)
video=out/"Draw_Test.mp4"
info=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_streams","-of","json",video]))["streams"][0]
total=scenes[-1]["endFrame"]
assert (info["width"],info["height"],info["avg_frame_rate"],int(info["nb_frames"])) == (1920,1080,"30/1",total)
subprocess.run(["ffmpeg","-v","error","-xerror","-i",video,"-f","null","-"],check=True)
frames=out/"frames"
frames.mkdir(exist_ok=True)
samples=[]
for scene in scenes:
    start=scene["drawingStart"]
    end=scene["lastContact"]
    for pct in (10,25,50,75,90,100):
        frame=round((start+(end-start)*pct/100)*30) if pct<100 else scene["endFrame"]-1
        samples.append((frame,f'{scene["id"]}-{pct:03d}.jpg'))
select="select='"+"+".join(f"eq(n,{frame})" for frame,_ in samples)+"',scale=960:540"
subprocess.run(["ffmpeg","-v","error","-i",video,"-vf",select,"-fps_mode","vfr","-threads","1",
                "-q:v","3",str(frames/"%03d.jpg")],check=True)
for n,(_,name) in enumerate(samples,1):
    (frames/f"{n:03d}.jpg").replace(frames/name)
for resource in ("draw-test.json","draw-report.json"):
    shutil.copy2(fixtures/resource,out/resource)
seconds, rss = performance.read_text().split()
summary=dict(frames=total,seconds=total/30,renderSeconds=float(seconds),peakProcessRssKiB=int(rss),
             fileBytes=video.stat().st_size,decodedWithoutError=True,sampleFrames=len(samples))
(out/"performance.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({"performance":summary}))
