"""Check the encoded demo and write the media, audio and feature reports for the artifact."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "studio/public/full-animation-demo"
OUT = Path(sys.argv[1])
VIDEO = OUT / "animation-test.mp4"


def command(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE).stdout


def probe(path):
    return json.loads(command("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)))["streams"]


def verify_video(path, width, height, fps, seconds):
    streams = probe(path)
    video = next(s for s in streams if s["codec_type"] == "video")
    assert (video["width"], video["height"], video["avg_frame_rate"], int(video["nb_frames"]),
            float(video["duration"]), video["codec_name"]) == (
            width, height, f"{fps}/1", fps * seconds, seconds, "h264"), video
    assert any(s["codec_type"] == "audio" for s in streams), "missing audio stream"
    command("ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-")
    return {"width": width, "height": height, "fps": fps, "seconds": seconds, "frames": fps * seconds}


def check_cues(path, expected, fps):
    raw = command("ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-")
    sound = np.frombuffer(raw, dtype="<f4")
    window = 80
    loud = np.max(np.abs(sound[:len(sound) // window * window].reshape(-1, window)), axis=1) > .025
    rising = np.flatnonzero(loud & ~np.r_[False, loud[:-1]]) * window / 16000
    assert len(rising) == len(expected), (rising, expected)
    measurements = []
    for cue, found in zip(expected, rising):
        quantized = math.floor(cue * fps + .5) / fps
        assert abs(found - quantized) < .04, (float(found), quantized)
        measurements.append({"requestedSeconds": cue, "frameTimeSeconds": quantized,
                             "detectedSeconds": float(found), "mediaDeltaMs": round((found - quantized) * 1000, 2)})
    return measurements


media = verify_video(VIDEO, 1920, 1080, 30, 150)
source_timing = json.loads((ASSETS / "timing.json").read_text())
browser = json.loads((OUT / "browser-checks.json").read_text())
measurements = check_cues(VIDEO, [w["start"] for w in source_timing["words"]], 30)
for measurement, word in zip(measurements, browser["visualWordCues"]):
    measurement["word"] = word["text"]
    measurement["visualFrame"] = math.ceil(word["start"] * 30 - 1e-8)
    measurement["audioVsVisualMs"] = round((measurement["detectedSeconds"] - measurement["visualFrame"] / 30) * 1000, 2)
    assert abs(measurement["audioVsVisualMs"]) < 1000 / 30

samples = {
    94: "writing-in-progress", 266: "writing-complete", 431: "geometry", 508: "svg-in-progress",
    710: "robot-trace-middle", 862: "robot-trace-end", 995: "rover-trace-middle", 1162: "rover-trace-end",
    1330: "robot-reveal-middle", 1448: "robot-reveal-end",
    1630: "rover-reveal-middle", 1748: "rover-reveal-end", 1964: "entrance-in-progress", 2063: "entrances-end",
    2158: "fade-in", 2329: "fade-out", 2427: "morph-start", 2535: "morph-middle", 2663: "morph-end",
    2717: "zoom-start", 2814: "zoom-peak", 2950: "zoom-end",
    3026: "scatter-start", 3078: "scatter-out", 3128: "scatter-middle", 3204: "scatter-back", 3248: "scatter-restored",
    3384: "drag-approach", 3442: "drag-contact", 3481: "drag-moving", 3569: "drag-complete",
    3717: "object-layers", 3872: "object-exit", 3890: "slide-left-seam", 4190: "slide-left-to-sync", 4280: "sync-cue",
}
frames = OUT / "frames"
frames.mkdir(exist_ok=True)
select = "select='" + "+".join(f"eq(n,{n})" for n in samples) + "'"
command("ffmpeg", "-v", "error", "-y", "-i", str(VIDEO), "-vf", select, "-fps_mode", "vfr",
        "-threads", "1", str(frames / "%02d.png"))
for i, (frame, label) in enumerate(samples.items(), 1):
    (frames / f"{i:02}.png").replace(frames / f"{frame:04}-{label}.png")
command("ffmpeg", "-v", "error", "-y", "-i", str(VIDEO), "-vf",
        select + ",scale=320:180,tile=6x6", "-frames:v", "1", "-threads", "1", "-update", "1",
        str(OUT / "sample-frames.png"))

assets = []
for name in ("El.png", "Kalem_El.png", "robot.png", "rover.png"):
    path = ASSETS / name
    with Image.open(path) as image:
        alpha = image.convert("RGBA").getchannel("A").getextrema()
        assert alpha == (0, 255), (name, alpha)
        assets.append({"file": name, "width": image.width, "height": image.height,
                       "alphaRange": alpha, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT / "assets.json").write_text(json.dumps(assets, indent=2) + "\n")
(OUT / "timing-report.json").write_text(json.dumps({
    "media": media, "syntheticCueMeasurements": measurements, "traceExtraction": source_timing["trace"],
}, indent=2, ensure_ascii=False) + "\n")

if len(sys.argv) > 2:
    endurance = Path(sys.argv[2])
    endurance_media = verify_video(endurance, 640, 360, 2, 1080)
    authored = json.loads((ASSETS / "endurance.json").read_text())
    cues = check_cues(endurance, [e["at"] for e in authored["sfx"]], 2)
    elapsed, peak = Path(sys.argv[3]).read_text().strip().split()
    (OUT / "endurance-report.json").write_text(json.dumps({
        "media": endurance_media, "sceneCount": len(authored["scenes"]), "elapsedSeconds": float(elapsed),
        "maxProcessRssKiB": int(peak),
        "maxAudioOffsetFromQuantizedFrameMs": max(abs(m["mediaDeltaMs"]) for m in cues),
        "maxCueQuantizationMs": round(max(abs(m["requestedSeconds"] - m["frameTimeSeconds"]) for m in cues) * 1000, 2),
        "wordCueCount": len(cues), "note": "Low-resolution proxy; peak RSS of highest-memory render process including children.",
    }, indent=2) + "\n")
