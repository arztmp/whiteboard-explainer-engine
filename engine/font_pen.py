"""Compose ordered pen routes with Be Vietnam Pro font ink.

A font outline gives the ink shape. The ordered routes below are independent
manual writing directions, normalized to the ink bounds, top-left origin.
Other Latin letters reuse the engine’s authored centerlines. No contour tracing is performed.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from math import ceil, dist
from unicodedata import normalize
from xml.sax.saxutils import quoteattr

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from .stroke_plan import THEME, pen_window, polyline, schedule
from .font_pen_symbols import authored_routes

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
    """Lay out font glyphs and mathematical notation as reusable pen strokes."""

    def __init__(self, font_file, color=THEME["navy"], *, subsets=()):
        self.fonts = []
        self.color = color
        for filename in (font_file, *subsets):
            # Keep the font open in memory for lazy glyph decomposition.
            font = TTFont(BytesIO(filename.read_bytes()))
            cmap = font.getBestCmap()
            font.flavor = None
            data = BytesIO()
            font.save(data)
            data.seek(0)
            self.fonts.append((font, cmap, ImageFont.truetype(data, 160)))
        self.units = self.fonts[0][0]['head'].unitsPerEm
        if any(font['head'].unitsPerEm != self.units for font, _, _ in self.fonts):
            raise ValueError('Font subsets must share unitsPerEm')
        self.cache = {}

    @classmethod
    def be_vietnam(cls, directory, *, weight=400, color=THEME["navy"]):
        """Load the npm package's Latin and Latin Extended faces at 400 or 600."""
        if weight not in (400, 600):
            raise ValueError('Pen writing supports weight 400 or 600')
        def file(subset):
            return directory / f'be-vietnam-pro-{subset}-{weight}-normal.woff'
        return cls(file('latin'), color, subsets=(file('latin-ext'), file('vietnamese')))

    def _source(self, char):
        for font, cmap, raster in self.fonts:
            glyph = cmap.get(ord(char))
            if glyph is not None:
                return font.getGlyphSet(), glyph, raster
        return None

    @staticmethod
    def _bounds(glyphs, name):
        bounds = BoundsPen(glyphs)
        glyphs[name].draw(bounds)
        return bounds.bounds

    def glyph(self, char):
        if char not in self.cache:
            source = self._source(char)
            if source is None:
                return None
            glyphs, name, raster = source
            x0,y0,x1,y1 = self._bounds(glyphs,name)
            width, height = x1-x0,y1-y0
            outline = SVGPathPen(glyphs)
            glyphs[name].draw(outline)
            color = quoteattr(self.color)
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                   f'viewBox="0 0 {width} {height}"><path transform="matrix(1 0 0 -1 {-x0} {y1})" '
                   f'fill={color} d="{outline.getCommands()}"/></svg>\n')
            routes, brush = self._register(char, raster, (x0,y0,x1,y1))
            self.cache[char] = GlyphInk(glyphs[name].width,(x0,y0,x1,y1),svg,routes,2*brush/160*self.units)
        return self.cache[char]

    def _design(self, char, bounds):
        if char in ROUTES:
            return ROUTES[char]
        if char == 'ı':
            return (((.5,.09),(.5,.91)),)
        if char == 'İ':
            return (((.5,.26),(.5,.93)), ((.5,.06),(.5,.09)))
        normalized = normalize('NFD',char)
        if len(normalized) == 2 and normalized[1] in '\u0308\u0306\u0327':
            base, mark = normalized
            ascenders = ((.34,.05),(.34,.08)), ((.66,.05),(.66,.08))
            marks = {'\u0308':ascenders, '\u0306':(((.28,.035),(.36,.10),(.50,.12),(.64,.10),(.72,.035)),),
                     '\u0327':(((.50,.72),(.43,.83),(.56,.88),(.50,.96),(.37,.97)),)}
            bx0,by0,bx1,by1 = self._bounds(*self._source(base)[:2])
            x0,y0,x1,y1 = bounds
            body = self._design(base,(bx0,by0,bx1,by1))
            return tuple(tuple(((bx0+x*(bx1-bx0)-x0)/(x1-x0),
                                (y1-by1+y*(by1-by0))/(y1-y0)) for x,y in route)
                         for route in body)+marks[mark]
        routes = authored_routes(char)
        xx, yy = zip(*(p for route in routes for p in route))
        x0,x1,y0,y1 = min(xx),max(xx),min(yy),max(yy)
        return tuple(tuple((.12+.76*(x-x0)/(x1-x0) if x1>x0 else .5,
                            .10+.80*(y-y0)/(y1-y0) if y1>y0 else .5) for x,y in route)
                     for route in routes)

    def _register(self, char, raster_font, bounds):
        # Register centerlines against ink; the exact silhouette remains vector.
        l,t,r,b = raster_font.getbbox(char,anchor='ls')
        raster = Image.new('L',(r-l,b-t))
        ImageDraw.Draw(raster).text((-l,-t),char,font=raster_font,anchor='ls',fill=255)
        ink = raster.crop(raster.getbbox())
        w,h = ink.size
        pixels = [(x+.5,y+.5) for y in range(h) for x in range(w) if ink.getpixel((x,y))]
        solid = [p for p in pixels if ink.getpixel((int(p[0]),int(p[1])))>=128]
        routes = []
        for route in self._design(char,bounds):
            registered = []
            for x,y in _sample(route,w,h):
                if not (0<=x<w and 0<=y<h and ink.getpixel((int(x),int(y)))>=128):
                    point = min(solid,key=lambda p:(p[0]-x)**2+(p[1]-y)**2)
                else:
                    point = x,y
                if not registered or dist(registered[-1],point)>=1:
                    registered.append(point)
            if len(registered)==1:
                # A dot uses a tiny movement inside the same ink pixel.
                x,y = registered[0]
                registered.append((x+.2,y))
            routes.append(registered)
        tips = [p for route in routes for p in route]
        # Curved punctuation is particularly sensitive to FreeType hinting
        # versus Chromium's unhinted SVG edges at these small sizes.
        padding = 9 if char in '?{}' else 4
        radius = max(min(dist(p,q) for q in tips) for p in pixels)+padding
        return tuple(tuple((x/w,y/h) for x,y in route) for route in routes), radius

    def _layout(self, expr, size):
        if isinstance(expr,str):
            x = 0
            items = []
            for char in normalize('NFC',expr):
                if char == ' ':
                    x += size*.32
                    continue
                ink = self.glyph(char)
                if ink is None:
                    # Be Vietnam Pro does not ship Greek and some math glyphs.
                    # Write those symbols using explicitly authored centerlines.
                    routes = authored_routes(char)
                    xx, yy = zip(*(p for route in routes for p in route))
                    left = min(xx)
                    strokes = [polyline([(x+(u-left+4)*size/100,(v-100)*size/100) for u,v in route],
                                        size*.064,color=self.color) for route in routes]
                    items.append((char,None,None,strokes))
                    x += (max(xx)-left+14)*size/100
                    continue
                x0,y0,x1,y1 = ink.bounds
                scale = size/self.units
                left,top = x+x0*scale,-y1*scale
                width,height = (x1-x0)*scale,(y1-y0)*scale
                strokes = [polyline([(left+px*width,top+py*height) for px,py in route],
                                     ink.brush*scale,color=self.color) for route in ink.routes]
                items.append((char,ink.svg,(left,top,width,height),strokes))
                x += ink.advance*scale
            return items,x
        kind,*parts = expr
        if kind == 'row':
            items,x = [],0
            for part in parts:
                child,width = self._layout(part,size)
                items.extend(_shift(child,x,0))
                x += width+.16*size
            return items,max(0,x-.16*size)
        if kind in ('sup','sub'):
            base, base_width = self._layout(parts[0],size)
            tail, tail_width = self._layout(parts[1],.62*size)
            return base+_shift(tail,base_width+.045*size,(-.57 if kind=='sup' else .27)*size),base_width+tail_width+.045*size
        if kind == 'fraction':
            numerator,nw = self._layout(parts[0],.82*size)
            denominator,dw = self._layout(parts[1],.82*size)
            width = max(nw,dw)+.26*size
            y = -.36*size
            above = y-.13*size-_edge(numerator, max)
            below = y+.13*size-_edge(denominator, min)
            bar = ('fraction bar',None,None,[polyline([(0,y),(width,y)],size*.064,color=self.color)])
            return _shift(numerator,(width-nw)/2,above)+[bar]+_shift(denominator,(width-dw)/2,below),width
        if kind == 'limits':
            symbol, sw = self._layout(parts[0],size)
            lower, lw = self._layout(parts[1],.52*size)
            upper, uw = self._layout(parts[2],.52*size)
            width = max(sw,lw,uw)
            top = _edge(symbol,min)-.10*size-_edge(upper,max)
            bottom = _edge(symbol,max)+.10*size-_edge(lower,min)
            return (_shift(symbol,(width-sw)/2,0)+_shift(lower,(width-lw)/2,bottom)
                    +_shift(upper,(width-uw)/2,top)),width
        if kind == 'root':
            body,bw=self._layout(parts[0],size)
            roof=_edge(body,min)-.13*size
            width=bw+.71*size
            route=polyline([(0,-.32*size),(.14*size,-.40*size),(.29*size,.06*size),
                            (.56*size,roof),(width,roof)],size*.064,color=self.color)
            return [('radical',None,None,[route])]+_shift(body,.64*size,0),width
        raise ValueError(f'Unknown formula node {kind!r}')

    def line(self, expr, center, baseline, size):
        """Return ordered character, SVG (or None), image box and stroke entries."""
        items,width = self._layout(expr,size)
        return _shift(items,center-width/2,baseline)


def _coordinates(stroke):
    return [tuple(map(float, part.split())) for part in stroke.d[1:].split(' L')]


def _edge(items, select):
    return select((y for _,_,_,strokes in items for stroke in strokes for _,y in _coordinates(stroke)), default=0)


def _shift(items, dx,dy):
    return [(char,svg,(box[0]+dx,box[1]+dy,*box[2:]) if box else None,
             [polyline([(x+dx,y+dy) for x,y in _coordinates(s)],s.width,color=s.color) for s in strokes])
            for char,svg,box,strokes in items]


def pen_writing(font, lines, *, asset_dir, asset_prefix, id_prefix, start, end,
                speed=1, hand_scale=.55, canvas=(1920,1080)):
    """Compile (text/formula, center, baseline, size) rows into native timeline elements."""
    if speed <= 0 or end <= start or start < .65:
        raise ValueError('Writing speed and time window must be positive')
    end = start+(end-start)/speed
    asset_dir.mkdir(parents=True,exist_ok=True)
    elements,strokes,targets = [],[],[]
    for expr,center,baseline,size,*face in lines:
        if size <= 0:
            raise ValueError('Writing size must be positive')
        for char,svg,box,routes in (face[0] if face else font).line(expr,center,baseline,size):
            target = None
            if svg is not None:
                name = f'u{ord(char):04x}-{sha256(svg.encode()).hexdigest()[:16]}.svg'
                (asset_dir/name).write_text(svg,encoding='utf-8')
                x,y,w,h = box
                target = f'{id_prefix}-glyph-{len(elements):03d}'
                elements.append(dict(id=target,type='image',src=f'{asset_prefix}/{name}',penPaint=True,
                                     x=x+w/2,y=y+h/2,w=w,h=h,enter='none'))
            strokes.extend(routes)
            targets.extend([target]*len(routes))
    paths = schedule(strokes,start,end,f'{id_prefix}-ink')
    for path,target in zip(paths,targets,strict=True):
        if target is not None:
            path['paintFor'] = {'imageId':target,'phase':'color'}
    return elements+paths,pen_window(start-.65,end+.65,*canvas,scale=hand_scale)
