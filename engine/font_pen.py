"""Pen routes for a Latin Be Vietnam Pro 600 specimen.

A font outline gives the ink shape. The ordered routes below are independent
manual writing directions, normalized to the ink bounds, top-left origin.
They cover the specimen alphabet only. No contour tracing is performed.
"""

from dataclasses import dataclass
from io import BytesIO
from math import ceil, dist

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from .stroke_plan import polyline

# Each tuple of points is one continuous movement. A new tuple lifts the pen.
ROUTES = {
    "-": (((.10,.50),(.90,.50)),),
    "0": (((.50,.08),(.25,.16),(.11,.38),(.12,.71),(.28,.90),(.53,.92),(.79,.82),(.90,.56),(.86,.30),(.72,.14),(.50,.08)),),
    "1": (((.10,.27),(.46,.21),(.76,.10),(.76,.91)),),
    "2": (((.13,.27),(.23,.14),(.47,.09),(.74,.13),(.85,.26),(.80,.40),(.61,.56),(.33,.73),(.13,.91),(.91,.91)),),
    "3": (((.17,.19),(.38,.09),(.67,.10),(.84,.20),(.84,.35),(.71,.45),(.46,.48),(.72,.51),(.88,.65),(.86,.79),(.67,.90),(.34,.91),(.16,.80)),),
    "4": (((.68,.10),(.12,.68),(.91,.68)), ((.73,.12),(.73,.91))),
    "5": (((.87,.09),(.31,.09),(.23,.47),(.46,.40),(.70,.44),(.85,.56),(.87,.73),(.73,.86),(.48,.92),(.25,.87),(.15,.74)),),
    "6": (((.83,.12),(.62,.10),(.39,.17),(.20,.37),(.11,.64),(.19,.82),(.39,.91),(.67,.91),(.85,.81),(.89,.66),(.80,.54),(.63,.46),(.38,.47),(.20,.59)),),
    "7": (((.09,.09),(.87,.09),(.68,.32),(.45,.56),(.36,.76),(.34,.91)),),
    "8": (((.52,.47),(.26,.36),(.17,.23),(.25,.12),(.50,.08),(.75,.12),(.83,.23),(.79,.36),(.52,.47),(.27,.57),(.13,.73),(.23,.86),(.48,.92),(.74,.89),(.87,.76),(.79,.61),(.52,.47)),),
    "9": (((.87,.46),(.73,.54),(.47,.54),(.23,.47),(.12,.34),(.15,.21),(.32,.11),(.57,.08),(.77,.14),(.87,.28),(.87,.51),(.76,.72),(.57,.86),(.30,.91),(.17,.87)),),
    "B": (((.12,.09),(.12,.92)), ((.14,.09),(.62,.09),(.81,.15),(.87,.27),(.81,.39),(.63,.45),(.15,.45)), ((.62,.45),(.85,.54),(.90,.69),(.86,.83),(.69,.91),(.15,.91))),
    "G": (((.86,.27),(.71,.14),(.50,.09),(.28,.14),(.13,.32),(.11,.56),(.22,.77),(.42,.90),(.69,.88),(.86,.74),(.90,.56),(.57,.56)),),
    "M": (((.09,.91),(.09,.10),(.50,.71),(.91,.10),(.91,.91)),),
    "P": (((.12,.09),(.12,.91)), ((.14,.09),(.60,.09),(.81,.15),(.88,.30),(.85,.45),(.70,.55),(.15,.56))),
    "T": (((.10,.08),(.90,.08)), ((.50,.10),(.50,.92))),
    "a": (((.77,.24),(.58,.13),(.34,.14),(.16,.35),(.13,.60),(.29,.83),(.51,.87),(.76,.74)), ((.87,.14),(.87,.86))),
    "b": (((.13,.11),(.13,.90)), ((.17,.52),(.33,.40),(.57,.37),(.78,.45),(.87,.63),(.81,.81),(.60,.91),(.35,.88),(.17,.77))),
    "d": (((.76,.48),(.56,.37),(.32,.41),(.16,.55),(.13,.72),(.26,.85),(.47,.91),(.70,.83),(.80,.74)), ((.87,.10),(.87,.90))),
    "e": (((.16,.49),(.88,.49),(.81,.28),(.69,.15),(.48,.12),(.27,.20),(.13,.41),(.13,.62),(.29,.82),(.51,.88),(.73,.81),(.83,.71)),),
    "h": (((.15,.10),(.15,.90)), ((.17,.52),(.32,.41),(.56,.38),(.75,.45),(.85,.56),(.85,.90))),
    "i": (((.50,.36),(.50,.90)), ((.50,.102),(.50,.125))),
    "l": (((.50,.11),(.50,.90)),),
    "m": (((.09,.15),(.09,.87)), ((.10,.36),(.22,.16),(.33,.13),(.45,.24),(.50,.43),(.50,.87)), ((.51,.35),(.64,.16),(.77,.13),(.88,.24),(.91,.42),(.91,.87))),
    "n": (((.15,.16),(.15,.87)), ((.17,.36),(.32,.17),(.55,.13),(.75,.21),(.85,.43),(.85,.87))),
    "o": (((.50,.12),(.28,.17),(.13,.37),(.14,.64),(.29,.82),(.51,.88),(.74,.81),(.87,.59),(.86,.37),(.72,.18),(.50,.12)),),
    "r": (((.20,.16),(.20,.87)), ((.23,.43),(.39,.23),(.61,.14),(.87,.15))),
    "t": (((.39,.12),(.39,.73),(.50,.85),(.67,.90),(.87,.90)), ((.14,.29),(.87,.29))),
    "v": (((.13,.12),(.50,.86),(.87,.12)),),
    "y": (((.13,.09),(.47,.67)), ((.87,.09),(.44,.84),(.29,.91),(.13,.91))),
}


@dataclass(frozen=True)
class GlyphInk:
    advance: float
    bounds: tuple
    svg: str
    routes: tuple
    brush: float


def _sample(route, width, height):
    points = [(x * width, y * height) for x, y in route]
    pixels = [points[0]]
    for (x, y), (u, v) in zip(points, points[1:]):
        steps = max(1, ceil(dist((x, y), (u, v))))
        pixels.extend((x + (u-x)*i/steps, y + (v-y)*i/steps) for i in range(1, steps+1))
    return pixels


class FontPen:
    """Pair exact font ink with ordered pen movements for supported glyphs."""

    def __init__(self, font_file, color):
        with TTFont(font_file) as font:
            self.glyphs = font.getGlyphSet()
            self.cmap = font.getBestCmap()
            self.units = font['head'].unitsPerEm
            self.color = color
            font.flavor = None
            data = BytesIO()
            font.save(data)
        data.seek(0)
        self.raster_font = ImageFont.truetype(data, 160)
        self.cache = {}

    def glyph(self, char):
        if char not in ROUTES:
            raise ValueError(f'No ordered Be Vietnam Pro pen route for {char!r}')
        if char not in self.cache:
            glyph = self.glyphs[self.cmap[ord(char)]]
            bounds = BoundsPen(self.glyphs)
            outline = SVGPathPen(self.glyphs)
            glyph.draw(bounds)
            glyph.draw(outline)
            x0, y0, x1, y1 = bounds.bounds
            w, h = x1-x0, y1-y0
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                   f'<path transform="matrix(1 0 0 -1 {-x0} {y1})" fill="{self.color}" '
                   f'd="{outline.getCommands()}"/></svg>\n')
            routes, brush = self._register(char)
            self.cache[char] = GlyphInk(glyph.width, bounds.bounds, svg, routes, brush)
        return self.cache[char]

    def _register(self, char):
        # Use the raster only to register authored movements and size the brush.
        # The rendered silhouette comes from the exact font's vector outline.
        l, t, r, b = self.raster_font.getbbox(char, anchor='ls')
        raster = Image.new('L', (r-l, b-t))
        ImageDraw.Draw(raster).text((-l,-t), char, font=self.raster_font, anchor='ls', fill=255)
        ink = raster.crop(raster.getbbox())
        w, h = ink.size
        solid = [(x+.5,y+.5) for y in range(h) for x in range(w) if ink.getpixel((x,y))>=128]
        routes = []
        for route in ROUTES[char]:
            registered = []
            for x, y in _sample(route, w, h):
                if ink.getpixel((int(x),int(y))) < 128:
                    point = min(solid, key=lambda p:(p[0]-x)**2+(p[1]-y)**2)
                else:
                    point = x, y
                if not registered or dist(registered[-1], point) >= 1:
                    registered.append(point)
            if len(registered)<2:
                raise ValueError(f'No measurable pen movement for {char!r}')
            routes.append(registered)
        # Cover corners and anti-aliasing, keeping each brush isolated to its glyph.
        pixels = [(x+.5,y+.5) for y in range(h) for x in range(w) if ink.getpixel((x,y))]
        tips = [p for route in routes for p in route]
        radius = max(min(dist(p,q) for q in tips) for p in pixels) + 2.5
        return tuple(tuple((x/w,y/h) for x,y in route) for route in routes), 2*radius/160*self.units

    def line(self, text, center, baseline, size):
        """Return ordered (character, SVG, image box, pen strokes) entries."""
        unsupported = sorted({c for c in text if c != ' ' and c not in ROUTES})
        if unsupported:
            raise ValueError(f'No ordered Be Vietnam Pro pen routes for {unsupported!r}')
        scale = size/self.units
        advances = [self.glyphs[self.cmap[ord(c)]].width for c in text]
        x = center - sum(advances)*scale/2
        result = []
        for char, advance in zip(text, advances):
            if char != " ":
                ink = self.glyph(char)
                x0,y0,x1,y1 = ink.bounds
                left, top = x+x0*scale, baseline-y1*scale
                width,height = (x1-x0)*scale,(y1-y0)*scale
                strokes = [polyline([(left+px*width,top+py*height) for px,py in route],
                                     ink.brush*scale,color=self.color) for route in ink.routes]
                result.append((char, ink.svg, (left,top,width,height), strokes))
            x += advance*scale
        return result
