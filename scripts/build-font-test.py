"""Build a standalone comparison timeline; rendering is a separate operation."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.font_pen import FontPen
from engine.handwriting import handwriting
from engine.scientific import formula_strokes
from engine.stroke_plan import THEME, pen_window, schedule

OUTPUT = ROOT/'studio/public/font-writing-test'
FONT = ROOT/'studio/node_modules/@fontsource/be-vietnam-pro/files/be-vietnam-pro-latin-600-normal.woff'
TEXT = ('The Three-Body Problem', 'Gravity and Motion', '1234567890')
INK = THEME['navy']
WIDTH, HEIGHT, FPS = 1920, 1080, 30
SIZE = 110
BASELINES = (385, 570, 755)
HAND = {"src":"/hand-motion-demo/Kalem_El.png","tip":{"x":98.5,"y":291.5},"scale":.42}


def text(id_, value, y, size, weight=600, font='sans'):
    return dict(id=id_, type='text', text=value, x=WIDTH/2, y=y, size=size,
                weight=weight, font=font, color=INK, mode='typography', align='center',
                enter='none')


def scene(scenes, id_, title, duration):
    start = scenes[-1]['end'] if scenes else 0
    result = dict(id=id_, start=start, end=start+duration, background='#ffffff',
                  transitionIn={'type':'none'}, elements=[text(id_+'-label',title,148,36)])
    scenes.append(result)
    return result


def timed(s, strokes, span, targets=None):
    start = s['start'] + 1.2
    end = start + span
    paths = schedule(strokes,start,end,s['id']+'-ink')
    if targets is not None:
        for path, image_id in zip(paths,targets,strict=True):
            path['paintFor'] = {'imageId':image_id,'phase':'color'}
    s['elements'].extend(paths)
    s['penTravel'] = pen_window(start-.66,end+.65, WIDTH,HEIGHT, scale=.55)


def main():
    glyph_dir = OUTPUT/'glyphs'
    glyph_dir.mkdir(parents=True, exist_ok=True)
    scenes = []
    for id_, family, weight, title in (
        ('be-vietnam-400','sans',400,'Be Vietnam Pro 400'),
        ('be-vietnam-600','sans',600,'Be Vietnam Pro 600'),
        ('be-vietnam-800','sans',800,'Be Vietnam Pro 800'),
        ('mali','hand',600,'Mali 600'),
    ):
        s = scene(scenes,id_,title,5)
        for i,(line,baseline) in enumerate(zip(TEXT,BASELINES)):
            s['elements'].append(text(f'{id_}-{i}',line,baseline-37,SIZE,weight,family))
    s = scene(scenes,'glyphs','GLYPHS · pen strokes',32)
    strokes = []
    for line, baseline in zip(TEXT,BASELINES):
        _, metrics = handwriting(line,0,baseline,SIZE)
        x = (WIDTH-metrics['lines'][0]['width'])/2
        row,_ = handwriting(line,x,baseline,SIZE,width=7.5,color=INK)
        strokes.extend(row)
    timed(s,strokes,26)

    s = scene(scenes,'be-vietnam-pen','Be Vietnam Pro 600 · pen strokes',32)
    font = FontPen(FONT,INK)
    strokes, targets = [], []
    for line,baseline in zip(TEXT,BASELINES):
        for char,svg,(x,y,w,h),routes in font.line(line,WIDTH/2,baseline,SIZE):
            name = f'u{ord(char):04x}.svg'
            (glyph_dir/name).write_text(svg,encoding='utf-8')
            element_id = f'{s["id"]}-glyph-{len(s["elements"]):02d}'
            s['elements'].append(dict(id=element_id,type='image',src=f'glyphs/{name}',penPaint=True,
                                      x=x+w/2,y=y+h/2,w=w,h=h,enter='none'))
            strokes.extend(routes)
            targets.extend([element_id]*len(routes))
    timed(s,strokes,26,targets)

    s = scene(scenes,'formula','Mathematical notation · pen strokes',19)
    equation = ('row','F','=','G',('fraction',('row',('sub','m','1'),('sub','m','2')),('sup','r','2')))
    strokes = formula_strokes(equation,0,0,162,color=INK,width=8)
    # The function returns already positioned strokes, so keep formula spacing
    # and use its glyph control bounds to center the whole expression.
    points = [tuple(map(float,pair)) for stroke in strokes
              for pair in re.findall(r'(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)',stroke.d)]
    xs,ys = zip(*points)
    x,y = (WIDTH-min(xs)-max(xs))/2, (HEIGHT-min(ys)-max(ys))/2+25
    timed(s,formula_strokes(equation,x,y,162,color=INK,width=8),13)

    plan = dict(style='B',width=WIDTH,height=HEIGHT,fps=FPS,duration=scenes[-1]['end'],
                hand=HAND,theme='brand',scenes=scenes)
    (OUTPUT/'Motor_Test.json').write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n',
                                          encoding='utf-8')


if __name__ == '__main__':
    main()
