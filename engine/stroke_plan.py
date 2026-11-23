"""Compile reusable pen paths to the engine's absolute-time path and penTravel schema."""
from dataclasses import dataclass
from math import dist
from pathlib import Path
import json

THEME = json.loads((Path(__file__).resolve().parents[1] / "studio/src/theme.json").read_text())


@dataclass
class Stroke:
    d: str
    start: tuple
    end: tuple
    length: float
    width: float
    region: int | None = None
    color: str = THEME["navy"]


def polyline(points, width, region=None, color=THEME["navy"]):
    d = "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in points)
    return Stroke(d, points[0], points[-1], sum(dist(a, b) for a, b in zip(points, points[1:])),
                  width, region, color)


def schedule(strokes, start, end, prefix):
    if not strokes or end <= start:
        raise ValueError("A pen plan needs paths and a positive time range")
    weights = [max(3, stroke.length) for stroke in strokes]
    minimum = .041
    lifts = [.044 + dist(a.end, b.start) / 1700 for a, b in zip(strokes, strokes[1:])]
    # Reserve pen-up intervals before distributing the remaining time by stroke length.
    budget = end - start - sum(lifts) - minimum * len(strokes)
    if budget <= 0:
        raise ValueError("The drawing interval does not leave time for pen-up travel")
    cursor = start
    total = sum(weights)
    result = []
    for i, (stroke, weight) in enumerate(zip(strokes, weights)):
        duration = minimum + budget * weight / total
        result.append(dict(id=f"{prefix}-{i:03d}", type="path", d=stroke.d, stroke=stroke.color,
                           strokeWidth=stroke.width, enter="draw", enterAt=round(cursor, 6),
                           enterDuration=round(duration, 6), hand=True))
        cursor += duration + (lifts[i] if i < len(lifts) else 0)
    return result


def pen_window(start, end, width=1920, height=1080, scale=.79):
    anchor = {"x": width * .55, "y": height + 220}
    return dict(start=start, end=end, scale=scale, lift=True, **{"from": anchor, "to": anchor})
