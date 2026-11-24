"""Layout authored centerline symbols into reusable rows, fractions and scripts."""
from dataclasses import replace
import re
from .handwriting import handwriting
from .stroke_plan import polyline


def _shift(stroke, dx, dy):
    def shift(match):
        return f"{float(match[1])+dx:.3f} {float(match[2])+dy:.3f}"
    d = re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", shift, stroke.d)
    return replace(stroke, d=d, start=(stroke.start[0]+dx, stroke.start[1]+dy),
                   end=(stroke.end[0]+dx, stroke.end[1]+dy))


def formula_strokes(expr, x, baseline, size, *, color, width=4.5):
    def box(value, s):
        if isinstance(value, str):
            paths, layout = handwriting(value, 0, 0, s, width=width, color=color)
            return paths, layout["lines"][0]["width"]
        kind, *args = value
        if kind == "row":
            paths, pos = [], 0
            for child in args:
                strokes, w = box(child, s)
                paths.extend(_shift(stroke, pos, 0) for stroke in strokes)
                pos += w + .18 * s
            return paths, pos - .18 * s
        if kind == "fraction":
            num, nw = box(args[0], .82*s)
            denom, dw = box(args[1], .82*s)
            length = max(nw, dw) + .32*s
            return ([_shift(p, (length-nw)/2, -.62*s) for p in num]
                    + [polyline([(0, -.4*s), (length, -.4*s)], width, color=color)]
                    + [_shift(p, (length-dw)/2, .47*s) for p in denom]), length
        if kind in {"sup", "sub"}:
            body, bw = box(args[0], s)
            extra, ew = box(args[1], .55*s)
            shift = -.53*s if kind == "sup" else .28*s
            return body + [_shift(p, bw+.04*s, shift) for p in extra], bw+ew+.04*s
        raise ValueError(f"Unknown formula layout: {kind}")

    paths, _ = box(expr, size)
    return [_shift(path, x, baseline) for path in paths]
