"""Analyze PNG/SVG geometry and compile pen strokes followed by local color fills."""
import base64
import io
import json
import math
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import feature, filters, measure, morphology, segmentation

from .stroke_plan import THEME, polyline, schedule
from .trace_map import order_skeleton


def svg_geometry(path, chrome):
    """Sample SVG's native geometry with resolved group transforms and preserve separate subpaths."""
    root = ElementTree.parse(path).getroot()
    forbidden = {"script", "foreignObject", "iframe", "object", "embed"}
    for element in root.iter():
        if element.tag.split("}")[-1] in forbidden or any(
            key.split("}")[-1].startswith("on")
            or (key.split("}")[-1] == "href" and not value.startswith("#"))
            or "url(" in value.lower() and "url(#" not in value.lower()
            for key, value in element.attrib.items()
        ):
            raise ValueError("SVG analysis supports self-contained, inert SVG assets")
        if element.tag.split("}")[-1] == "style" and any(
            token in (element.text or "").lower() for token in ("url(", "@import")
        ):
            raise ValueError("Use inline SVG paint or self-contained definitions")
    ElementTree.register_namespace("", "http://www.w3.org/2000/svg")
    markup = ElementTree.tostring(root, encoding="utf-8")
    adapter = Path(__file__).resolve().parents[1] / "studio/scripts/analyze-svg.cjs"
    output = subprocess.run(["node", str(adapter), chrome], input=markup, capture_output=True,
                            timeout=40, check=True).stdout
    result = json.loads(output)
    raster = Image.open(io.BytesIO(base64.b64decode(result["png"].split(",")[1]))).convert("RGBA")
    return raster, result["paths"], (result["width"], result["height"])


def raster_edges(image):
    rgba = np.asarray(image, dtype=np.float32) / 255
    alpha = rgba[:, :, 3] > .26
    rgb = rgba[:, :, :3] * rgba[:, :, 3, None] + (1 - rgba[:, :, 3, None])
    gray = rgb @ np.array([.2126, .7152, .0722])
    silhouette = alpha & ~ndimage.binary_erosion(alpha)
    internal = ndimage.binary_erosion(alpha, iterations=2)
    canny = feature.canny(gray, sigma=1.05, low_threshold=.034, high_threshold=.09) & internal
    chromatic = np.maximum.reduce([filters.sobel(filters.gaussian(rgb[:, :, i], .85)) for i in range(3)])
    band = morphology.skeletonize((chromatic > .095) & internal)
    edges = morphology.skeletonize(canny | band)
    return silhouette, edges, chromatic, {"cannyPixels": int(canny.sum()), "colorGradientPixels": int(band.sum()),
                                         "combinedInteriorPixels": int(edges.sum())}


def regions(image, strength):
    alpha = np.asarray(image)[:, :, 3] > 0
    h, w = alpha.shape
    ys, xs = np.nonzero(alpha)
    if not len(xs):
        raise ValueError("Transparent assets have no paths to draw")
    markers = np.zeros((h, w), dtype=np.int32)
    centers = []
    columns = max(3, min(7, round(5 * math.sqrt((np.ptp(xs) + 1) / (np.ptp(ys) + 1)))))
    rows = max(3, min(6, round(21 / columns)))
    yb = np.linspace(ys.min(), ys.max() + 1, rows + 1).astype(int)
    xb = np.linspace(xs.min(), xs.max() + 1, columns + 1).astype(int)
    for iy in range(rows):
        for ix in range(columns):
            y0, y1 = yb[iy:iy+2]
            x0, x1 = xb[ix:ix+2]
            py, px = np.nonzero(alpha[y0:y1, x0:x1])
            if not len(px):
                continue
            nearest = np.argmin((py - (y1-y0)/2)**2 + (px - (x1-x0)/2)**2)
            y, x = int(py[nearest] + y0), int(px[nearest] + x0)
            centers.append((y, x))
            markers[y, x] = len(centers)
    labels = segmentation.watershed(strength, markers, compactness=.003)
    masks = []
    for label in range(1, len(centers) + 1):
        contours = measure.find_contours(np.pad(labels == label, 1), .5)
        d = []
        for contour in contours:
            points = measure.approximate_polygon(contour - .5, tolerance=.42)
            d.append("M" + " L".join(f"{x/w:.5f} {y/h:.5f}" for y, x in points) + "Z")
        masks.append(" ".join(d))
    return labels, masks


def analyze(path, chrome, resolution=540):
    if path.suffix.lower() == ".svg":
        image, vectors, original = svg_geometry(path, chrome)
    else:
        with Image.open(path) as source:
            original = source.size
            image = source.convert("RGBA")
            image.thumbnail((resolution, resolution))
        vectors = None
    h, w = image.height, image.width
    shell, inner, strength, detectors = raster_edges(image)
    labels, masks = regions(image, strength)
    source = []
    if vectors is not None:
        source = [(False, np.array([(y * h, x * w) for x, y in route])) for route in vectors if len(route)>1]
    else:
        for exterior, image_edges in ((True, shell), (False, inner)):
            source.extend((exterior, np.asarray(route)) for route in order_skeleton(image_edges) if len(route) >= 2)
    candidates = []
    for exterior, route in source:
        if vectors is not None or len(route) < 18:
            chunks = [route]
        else:
            coords = np.clip(route.astype(int), 0, [h-1, w-1])
            tags = ndimage.median_filter(labels[coords[:, 0], coords[:, 1]], size=11, mode="nearest")
            cuts = np.flatnonzero(tags[1:] != tags[:-1]) + 1
            chunks = []
            start = 0
            for stop in cuts:
                if stop - start >= 20 and len(route) - stop >= 12:
                    chunks.append(route[start:stop+1])
                    start = stop
            chunks.append(route[start:])
        for chunk in chunks:
            y, x = np.clip(chunk[len(chunk)//2].astype(int), 0, [h-1, w-1])
            label = int(labels[y, x])-1
            length = np.linalg.norm(np.diff(chunk, axis=0), axis=1).sum()
            candidates.append((exterior, length, label, chunk))
    low = image.copy()
    low.thumbnail((270, 270))
    _, _, _, low_metrics = raster_edges(low)
    return dict(candidates=candidates, masks=masks, imageSize=(w, h), original=original,
                isSvg=vectors is not None, detectors=detectors, lowMetrics=low_metrics)


def compile_illustration(analysis, src, prefix, center, width, start, end, *, mode="full", limit=46):
    """Emit native pen paths plus independently timed SVG mask regions for full mode."""
    if mode not in {"trace", "full"}:
        raise ValueError(f"Unsupported illustration planning mode: {mode}")
    w, h = analysis["imageSize"]
    ratio = width / w
    height = width * analysis["original"][1] / analysis["original"][0]
    x0, y0 = center[0]-width/2, center[1]-height/2
    regions_ = {}
    for exterior, length, region, route in analysis["candidates"]:
        if length >= (2 if analysis["isSvg"] else 8):
            regions_.setdefault(region, []).append((exterior, length, route))
    ranked = sorted(regions_, key=lambda n: (
        int(np.median(np.concatenate([p[:, 0] for _, _, p in regions_[n]])) / (h/5)),
        np.median(np.concatenate([p[:, 1] for _, _, p in regions_[n]]))))
    keep = {}
    if analysis["isSvg"]:
        keep = regions_
    else:
        def importance(item):
            exterior, length, _ = item
            return length * (.78 if exterior else 1.3)

        regional = {n: sorted(group, key=importance, reverse=True) for n, group in regions_.items()}
        keep = {label: group[:1] for label, group in regional.items()}
        exterior_count = sum(group[0][0] for group in keep.values())
        exterior_limit = max(exterior_count, round(limit * .38))
        remaining = sorted(((label, item) for label, group in regional.items() for item in group[1:]),
                           key=lambda choice: importance(choice[1]), reverse=True)
        selected = len(keep)
        for label, item in remaining:
            if selected >= limit:
                break
            if item[0] and exterior_count >= exterior_limit:
                continue
            keep[label].append(item)
            exterior_count += item[0]
            selected += 1
    ordered = []
    previous = np.array([0., 0.])
    for region in ranked:
        candidates = list(keep[region])
        while candidates:
            _, i, reverse = min(
                (np.linalg.norm(previous - item[2][j]) + (0 if item[0] else 35), i, j == -1)
                for i, item in enumerate(candidates) for j in (0, -1))
            exterior, length, route = candidates.pop(i)
            if reverse:
                route = route[::-1]
            previous = route[-1]
            points = measure.approximate_polygon(route, tolerance=.7 if not analysis["isSvg"] else .35)
            pts = [(x0 + x * ratio, y0 + y * height / h) for y, x in points]
            if len(pts) < 2:
                continue
            ordered.append((exterior, length, region, polyline(pts, 2.8 if exterior else 1.85, region)))
    strokes = schedule([row[3] for row in ordered], start, end - (.58 if mode == "full" else 0), prefix)
    fills = []
    if mode == "full":
        for region, mask in enumerate(analysis["masks"]):
            local = [stroke for stroke, row in zip(strokes, ordered) if row[2] == region]
            fraction = (region+1)/len(analysis["masks"])
            at = local[0]["enterAt"] + local[0]["enterDuration"] * .7 if local else start + (end-start)*fraction*.84
            complete = max(at + .28, local[-1]["enterAt"] + local[-1]["enterDuration"] + .38) if local else at + .65
            complete = min(end, complete)
            fills.append(dict(d=mask, at=at, end=complete))
            for stroke in local:
                stroke["inkFade"] = dict(at=max(at, stroke["enterAt"] + stroke["enterDuration"]), end=complete)
        strokes.insert(0, dict(id=f"{prefix}-color", type="image", src=src, x=center[0], y=center[1], w=width,
                               h=height, enter="none", enterAt=start,
                               illustration=dict(regions=fills), z=-1))
    source = analysis["candidates"]
    detected_outer = sum(row[0] for row in source)
    drawn_outer = sum(row[0] for row in ordered)
    return strokes, {
        "source": src, "mode": mode, "displayWidth": width,
        "originalSize": analysis["original"], "analysisSize": analysis["imageSize"],
        "detectedExteriorPaths": detected_outer, "detectedInteriorOrNativePaths": len(source)-detected_outer,
        "drawnExteriorPaths": drawn_outer, "drawnInteriorOrNativePaths": len(ordered)-drawn_outer,
        "omittedPaths": len(source)-len(ordered), "fillRegions": len(fills),
        "retainedPathLengthRatio": round(sum(row[1] for row in ordered)/max(1,sum(row[1] for row in source)), 4),
        "edgeDetection": analysis["detectors"], "lowerResolutionDetection": analysis["lowMetrics"],
    }
