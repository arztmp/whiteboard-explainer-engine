"""Layout authored centerline symbols into reusable rows, fractions and scripts."""
from dataclasses import replace
import re
from .handwriting import GLYPHS, handwriting
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
            unsupported = sorted({c for c in value if not c.isspace() and c not in GLYPHS})
            if unsupported:
                raise ValueError(f"Unsupported handwritten formula symbols: {', '.join(unsupported)}")
            if not value.strip():
                return [], 0
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
        if kind == "root":
            body, bw = box(args[0], s)
            left = .37*s
            # Clear the authored exponent strokes as well as the main radicand.
            roof = min(-.97*s, min((float(y) for p in body for _, y in
                                    re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", p.d)), default=0) - .11*s)
            length = bw + left + .12*s
            radical = polyline([(0, -.31*s), (.095*s, -.38*s), (.20*s, .03*s),
                                (left, roof), (length, roof)], width, color=color)
            return [radical] + [_shift(p, left+.045*s, 0) for p in body], length
        if kind in {"limits", "integral"}:
            body, bw = box("∑" if kind == "limits" else "∫", s)
            lower, lw = box(args[0], .48*s)
            upper, uw = box(args[1], .48*s)
            if kind == "integral":
                return (body + [_shift(p, bw*.67, .34*s) for p in lower]
                        + [_shift(p, bw*.91, -.72*s) for p in upper], bw + max(lw, uw))
            length = max(bw, lw, uw)
            return ([_shift(p, (length-bw)/2, 0) for p in body]
                    + [_shift(p, (length-lw)/2, .55*s) for p in lower]
                    + [_shift(p, (length-uw)/2, -1.06*s) for p in upper]), length
        if kind in {"sup", "sub"}:
            body, bw = box(args[0], s)
            extra, ew = box(args[1], .55*s)
            shift = -.53*s if kind == "sup" else .28*s
            return body + [_shift(p, bw+.04*s, shift) for p in extra], bw+ew+.04*s
        raise ValueError(f"Unknown formula layout: {kind}")

    paths, _ = box(expr, size)
    return [_shift(path, x, baseline) for path in paths]
