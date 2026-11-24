"""Decode the acceptance MP4 and package checks against the authored timeline."""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

out = Path(sys.argv[1])
perf_path = Path(sys.argv[2])
asset_dir = Path(__file__).resolve().parents[1] / "studio/public/motor-demo"
timeline = json.loads((asset_dir / "timeline.json").read_text())
manifest = json.loads((asset_dir / "report.json").read_text())
video = out / "Motor_Test.mp4"


def run(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, check=True).stdout


streams = json.loads(run("ffprobe","-v","error","-show_streams","-of","json",str(video)))["streams"]
v = next(s for s in streams if s["codec_type"]=="video")
duration = timeline["duration"]
assert (v["width"],v["height"],v["avg_frame_rate"],int(v["nb_frames"]),float(v["duration"])) == (
    1920,1080,"30/1",duration*30,duration)
assert any(s["codec_type"]=="audio" for s in streams)
run("ffmpeg","-v","error","-xerror","-i",str(video),"-f","null","-")

decoded = run("ffmpeg","-v","error","-i",str(video),"-vn","-f","f32le","-ar","16000","-ac","1","-")
pcm = np.frombuffer(decoded,dtype="<f4")
n = 80
loud = np.max(np.abs(pcm[:len(pcm)//n*n].reshape(-1,n)),axis=1)>.023
onsets = np.flatnonzero(loud & ~np.r_[False,loud[:-1]])*n/16000
assert len(onsets)==len(manifest["cues"]),onsets
timing = []
for word, signal in zip(manifest["cues"],onsets):
    frame = math.ceil(word["start"]*30-1e-8)
    delta = (signal-frame/30)*1000
    assert abs(delta)<1000/30
    timing.append(dict(cue=word["text"],expectedVisualFrame=frame,measuredAudioSeconds=signal,deltaMs=round(delta,3)))
(out/"audio.json").write_text(json.dumps({"type":"synthetic","narration":"NOT TESTED","cues":timing},indent=2)+"\n")

samples={}
for i,scene in enumerate(manifest["scenes"],1):
    start,end=scene["start"],scene["end"]
    points=(.08,.23,.48,.76,.88) if scene["id"] in {"background","handwriting","layers","bg-two","reassemble",
        "full-one","full-two","morph","zoom","scatter","explainer"} else (.23,.58,.81)
    for j,p in enumerate(points,1):
        samples[round((start+p*(end-start))*30)] = f'{i:02}-{scene["id"]}-{j}'
samples=dict(sorted(samples.items()))
folder=out/"frames"
folder.mkdir(exist_ok=True)
select="select='"+"+".join(f"eq(n,{f})" for f in samples)+"',scale=720:404"
run("ffmpeg","-v","error","-i",str(video),"-vf",select,"-fps_mode","vfr","-threads","1","-q:v","3",str(folder/"%03d.jpg"))
for j,name in enumerate(samples.values(),1):
    (folder/f"{j:03}.jpg").replace(folder/f"{name}.jpg")
elapsed, peak = perf_path.read_text().split()
media=dict(durationSeconds=duration,frames=duration*30,width=1920,height=1080,fps=30,
           elapsedSeconds=float(elapsed),renderedFps=round(duration*30/float(elapsed),2),
           maxSingleProcessRssKiB=int(peak),bytes=video.stat().st_size,sceneCount=len(timeline["scenes"]),
           uploadedSourceFiles=len(manifest["assets"]),uniqueUploadedSources=len({a["sha256"] for a in manifest["assets"]}),
           animationElementCount=sum(e["enter"]!="none" or any(e.get(k) for k in ("moves","carry","scatter","zoom","exit","illustration"))
                                     for sc in timeline["scenes"] for e in sc["elements"]),
           samples=len(samples),decodeErrors=0,est25MinSeconds=round(float(elapsed)*1500/duration,1))
(out/"performance.json").write_text(json.dumps(media,indent=2)+"\n")
(out/"assets.json").write_text(json.dumps(manifest["assets"],indent=2)+"\n")
(out/"trace.json").write_text(json.dumps(manifest["coverage"],indent=2)+"\n")
(out/"scenes.json").write_text(json.dumps(manifest["scenes"],indent=2)+"\n")
shutil.copy2(asset_dir/"timeline.json",out/"timeline.json")
print(json.dumps({"performance":media,"audio":timing}))
