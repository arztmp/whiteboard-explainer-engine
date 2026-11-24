"""Plan image contact paths before rendering. All widths are in scene pixels."""
from math import ceil, dist
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import measure

from .illustration import analyze, raster_edges
from .stroke_plan import THEME, polyline


def _length(points):
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def _nearby_order(routes, previous):
    while routes:
        i, reverse = min(((i, rev) for i in range(len(routes)) for rev in (False, True)),
                         key=lambda option: dist(previous, routes[option[0]][0][-1 if option[1] else 0]))
        points, *rest = routes.pop(i)
        if reverse:
            points = points[::-1]
        previous = points[-1]
        yield points, *rest


def _cover(coverage, points, radius):
    # Rasterize the centerline locally. Reserve two analysis pixels for rounding,
    # display sampling and the antialiased outer edge of the browser's brush.
    pad = ceil(radius) + 2
    lo = np.maximum(np.floor(points.min(axis=0)).astype(int)-pad, 0)
    hi = np.minimum(np.ceil(points.max(axis=0)).astype(int)+pad+1, coverage.shape)
    if np.any(hi <= lo):
        return coverage[:0, :0], coverage[:0, :0], lo, hi
    raster = Image.new("1", (int(hi[1]-lo[1]), int(hi[0]-lo[0])))
    ImageDraw.Draw(raster).line([tuple(p[::-1]) for p in points-lo], fill=1)
    hit = ndimage.distance_transform_edt(~np.asarray(raster)) <= radius-2
    return hit, coverage[lo[0]:hi[0], lo[1]:hi[1]], lo, hi


def _paint_routes(image, strength, alpha):
    height, width = alpha.shape
    # Signed distance follows the shape and its holes. Inset contours wrap
    # irregular regions; luminance and color boundaries bend their trajectories.
    inside = ndimage.distance_transform_edt(np.pad(alpha, 1))[1:-1, 1:-1]
    outside = ndimage.distance_transform_edt(~alpha)
    density = ndimage.gaussian_filter(strength, 3)
    rgb = np.asarray(image, dtype=float)[:, :, :3] / 255
    luminance = ndimage.gaussian_filter(rgb @ np.array([.2126, .7152, .0722]), 4)
    field = ndimage.gaussian_filter(inside-outside, 1.65) + 5*(luminance-.5)
    uncovered = alpha.copy()
    routes = []

    def add(points, radius, minimum):
        hit, patch, _, _ = _cover(uncovered, points, radius)
        if np.count_nonzero(patch & hit) < minimum:
            return
        patch[hit] = False
        routes.append((points, float(radius), "color"))

    for level in np.arange(3, field.max()+1, 16):
        for contour in measure.find_contours(np.pad(field, 1, constant_values=-40), level):
            points = measure.approximate_polygon(contour-1, tolerance=.65)
            if _length(points) < 8:
                continue
            indices = np.clip(np.round(points).astype(int), 0, [height-1, width-1])
            local = density[indices[:, 0], indices[:, 1]]
            radius = np.clip(14 + min(level, 30)*.16 - np.quantile(local, .7)*18, 8, 20)
            add(points, radius, 16)

    # Follow the medial curves of remaining areas. Small isolated alpha details
    # are touched explicitly too, with a short nonzero stroke at the contact point.
    for _ in range(4):
        if not uncovered.any():
            break
        missing = ndimage.gaussian_filter(uncovered.astype(float), 2)
        for contour in measure.find_contours(np.pad(missing, 1), .42):
            points = measure.approximate_polygon(contour-1, tolerance=.8)
            if _length(points) >= 7:
                add(points, 10, 12)
    while uncovered.any():
        ys, xs = np.where(uncovered)
        count = ndimage.uniform_filter(uncovered.astype(float), size=13)
        i = int(np.argmax(count[ys, xs]))
        y, x = ys[i], xs[i]
        direction = ndimage.gaussian_filter(field, 2)
        dy = direction[min(y+1,height-1),x]-direction[max(y-1,0),x]
        dx = direction[y,min(x+1,width-1)]-direction[y,max(x-1,0)]
        tangent = np.array([-dx,dy])
        tangent /= max(np.linalg.norm(tangent), .001)
        if not tangent.any():
            tangent = np.array([1., 1.]) / np.sqrt(2)
        points = np.array([[y,x]-tangent*1.4, [y,x]+tangent*1.4])
        add(points, 9, 1)
    return routes


def _shading_families(paths):
    """Find repeated straight tracks near each other, with no invented ink."""
    tracks = []
    for index, (points, _, _) in enumerate(paths):
        length = _length(points)
        axis = points[-1] - points[0]
        span = np.linalg.norm(axis)
        if 5 <= length <= 42 and span >= .81*length:
            tracks.append((index, points.mean(axis=0), axis/span))
    families = {}
    for index, center, axis in tracks:
        parallel = cross = 0
        for other_index, other_center, other_axis in tracks:
            if index == other_index:
                continue
            offset = other_center-center
            if np.linalg.norm(offset) > 20:
                continue
            alignment = abs(np.dot(axis, other_axis))
            separation = abs(np.dot(offset, [-axis[1],axis[0]]))
            if alignment > .94 and 1.4 < separation < 12:
                parallel += 1
            elif alignment < .74 and separation < 11:
                cross += 1
        if parallel >= 2:
            families[index] = "crossHatchCandidates" if cross >= 2 else "hatchCandidates"
    return families


def _ink_routes(profile, strength, ratio, full):
    chosen = {"outline": [], "detail": []}
    total = {"outline": 0., "detail": 0.}
    for exterior, length, _, raw in profile["candidates"]:
        phase = "outline" if exterior else "detail"
        total[phase] += length * ratio
        points = measure.approximate_polygon(raw, tolerance=.55 if full else .83)
        if len(points) < 2:
            continue
        y, x = np.round(points).astype(int).T
        y, x = np.clip(y,0,strength.shape[0]-1), np.clip(x,0,strength.shape[1]-1)
        contrast = float(np.quantile(strength[y,x], .65))
        # Require screen-space significance. FULL admits shorter, moderate-contrast
        # lines and fine shading. Selection has no hard count ceiling.
        threshold = 23 if exterior else (33 if full else 92)
        if length*ratio*(1+min(1, 3*contrast)) >= threshold:
            chosen[phase].append((points, 1.05 if full else 1.45, phase))
    # Pick extended, high-contrast structural paths first. The useful detail
    # length grows with image complexity rather than a fixed number of strokes.
    detail_budget = (43 if full else 25) * np.sqrt(total["detail"])
    pool = chosen["detail"]
    order = sorted(range(len(pool)), key=lambda i: -_length(pool[i][0]))
    chosen["detail"] = []
    kept = set()
    used = 0.
    for index in order:
        path = pool[index]
        length = _length(path[0])*ratio
        if used + length <= detail_budget:
            chosen["detail"].append(path)
            kept.add(index)
            used += length
    families = _shading_families(pool) if full else {}
    shading = []
    extra = 0.
    for index in sorted(families, key=lambda i: (families[i] != "crossHatchCandidates", -_length(pool[i][0]))):
        if index in kept:
            continue
        length = _length(pool[index][0])*ratio
        if extra + length <= .13*detail_budget:
            shading.append(pool[index])
            kept.add(index)
            extra += length
    coverage = {phase: {"selected": len(paths), "selectedEdgeLengthPx": round(sum(_length(p)*ratio for p, _, _ in paths)),
                        "candidateEdgeLengthPx": round(total[phase])} for phase, paths in chosen.items()}
    if full:
        coverage["detail"]["selected"] += len(shading)
        coverage["detail"]["selectedEdgeLengthPx"] += round(extra)
        coverage["detail"]["shading"] = {
            family: {"detected": sum(v==family for v in families.values()),
                     "selected": sum(families.get(i)==family for i in kept)}
            for family in ("hatchCandidates", "crossHatchCandidates")
        }
        # Keep texture marks together after the larger structural details.
        chosen["shading"] = shading
    return chosen, coverage


def compile_paint(source: Path, src, mode, center, width, start, chrome, *, prefix):
    if mode not in {"reveal", "draw", "full"}:
        raise ValueError(f"Unknown pen-paint mode: {mode}")
    with Image.open(source) as original:
        w, h = original.size
        image = original.convert("RGBA")
        height = round(h/w*width)
        resolution = 278 if mode == "full" else 230
        alpha = image.getchannel("A").point(lambda value: 255 if value else 0)
        image.thumbnail((resolution, resolution), Image.Resampling.BOX)
        support = np.asarray(alpha.resize(image.size,Image.Resampling.BOX)) > 0
        support = ndimage.binary_dilation(support, iterations=1)
    _, _, strength, _ = raster_edges(image)
    ratio = width/image.width
    color = _paint_routes(image, strength, support)
    groups, coverage = ({"outline": [], "detail": []}, {})
    if mode != "reveal":
        groups, coverage = _ink_routes(analyze(source, chrome, resolution=resolution, connect=True),
                                       strength, ratio, mode == "full")
    color_count = len(color)
    paths = []
    previous = (image.height*.92, image.width*.85)
    clock = start
    image_id = f"{prefix}-art"
    for group in (*groups.values(), color):
        for points, radius, phase in _nearby_order(group, previous):
            coords = [(round(center[0]-width/2+(x+.5)*ratio, 3),
                       round(center[1]-height/2+(y+.5)*height/image.height, 3)) for y,x in points]
            ink = polyline(coords, 2*radius*(ratio if phase == "color" else 1), color=THEME["navy"])
            if ink.length <= .01:
                continue
            clock += max(.107, dist(previous, points[0])*ratio/1050)
            # easeDraw slightly accelerates/decelerates each stroke. Schedule
            # sufficient time for moderate peak speeds even on complex assets.
            duration = max(.14, ink.length/(575 if phase == "color" else 515))
            paths.append(dict(id=f"{prefix}-paint-{len(paths):03d}", type="path", d=ink.d, stroke=ink.color,
                              strokeWidth=ink.width, rough=False, hand=True, enter="draw",
                              enterAt=round(clock, 6), enterDuration=round(duration, 6),
                              paintFor=dict(imageId=image_id, phase=phase)))
            clock += duration
            previous = points[-1]
    image_element = dict(id=image_id,type="image",src=src,x=center[0],y=center[1],w=width,h=height,
                         enter="none",penPaint=True)
    report = dict(mode=mode, source=src, analysisSize=image.size, edgeCoverage=coverage,
                  colorRoutes=color_count, strokeCount=len(paths), requiredSeconds=round(clock-start, 3))
    return [image_element, *paths], clock, report
