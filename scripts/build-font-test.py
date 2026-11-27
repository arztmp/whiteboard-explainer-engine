"""Build the standalone writing test without rendering a video."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.formula_plan import formula_element, validate_formulas
from engine.font_pen import FontPen, pen_writing
from engine.stroke_plan import THEME

OUTPUT = ROOT/'studio/public/font-writing-test'
FONTS = ROOT/'studio/node_modules/@fontsource/be-vietnam-pro/files'
WIDTH, HEIGHT, FPS = 1920, 1080, 30
TEXT = ('The Three-Body Problem', 'Gravity and Motion', '1234567890')
HAND = {"src":"/hand-motion-demo/Kalem_El.png","tip":{"x":98.5,"y":291.5},"scale":.42}


def main():
    scenes=[]
    def scene(id_,duration):
        start = scenes[-1]['end'] if scenes else 0
        s=dict(id=id_,start=start,end=start+duration,background='#ffffff',
               transitionIn={'type':'none'},elements=[])
        scenes.append(s)
        return s

    def rows(lines,size,baselines=(360,545,730),center=960):
        return [(expr,center,y,size) for expr,y in zip(lines,baselines,strict=True)]

    def write(id_,font,rows_,seconds,*,speed=1):
        s=scene(id_,seconds/speed+5)
        start=s['start']+1.2
        s['elements'],s['penTravel']=pen_writing(font,rows_,asset_dir=OUTPUT/'glyphs',
            asset_prefix='glyphs',id_prefix=id_,start=start,end=start+seconds,speed=speed)
        # Keep the scene boundaries on native frame boundaries.
        s['end']=round(s['end']*FPS)/FPS

    body=FontPen.be_vietnam(FONTS)
    title=FontPen.be_vietnam(FONTS,weight=600)
    blue=FontPen.be_vietnam(FONTS,color='#184c72')
    write('title-600',title,rows((TEXT[0],),120,(565,)),12)
    write('body-400',body,rows(TEXT,110),29)
    write('latin',body,rows(('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz','0123456789'),91),34)
    write('turkish-german',blue,rows(('ÇĞİÖŞÜ çğıöşü','ÄÖÜ äöü ß ẞ','İğne, ölçü! Grüße?'),105),28,speed=1.15)
    write('punctuation',body,rows(('.,:;!? … – —','“Text” (x) [y] {z}','# % & @ * / \\ | _ $ € ^ ~ `'),96),27)
    write('greek',body,rows(('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ','αβγδεζηθικλμνξοπρστυφχψως','µ ϕ ϑ ϖ'),94),34)
    write('symbols',body,rows(('+ − × ÷ ± = ≈ ≠ < > ≤ ≥','∞ √ ∑ ∏ ∫ ∂ ∇ ° ·','→ ↔ ∝ ∈ ∅ ⊥ ′ ″'),99),29)
    formula=('row','F = G',('fraction',('row',('sub','m','1'),('sub','m','2')),('sup','r','2')))
    root=('row','x =',('root',('row',('sup','a','2'),' + ',('sup','b','2'))))
    write('formula-400',body,rows((formula,root),131,(385,780)),23)
    s=scene('katex-formulas',13)
    for i,(latex,y) in enumerate((
        (r'F = G \frac{m_1m_2}{r^2}', 255),
        (r'\int_0^L f(x)\,dx, \quad \frac{\mathrm{d}}{\mathrm{d}t}\vec{r}(t)', 525),
        (r'\sum_{n=1}^{N}\sqrt{\alpha_n^2+\beta_n^2}', 810),
    )):
        s['elements'].append(formula_element(f'katex-{i}',latex,x=960,y=y,size=104,
            color=THEME['navy'],start=s['start']+1+i*2.1,duration=.7))
    validate_formulas(scenes,ROOT/'studio')
    timeline=dict(style='B',width=WIDTH,height=HEIGHT,fps=FPS,duration=scenes[-1]['end'],
                  hand=HAND,theme='brand',scenes=scenes)
    (OUTPUT/'Motor_Test.json').write_text(json.dumps(timeline,ensure_ascii=False,separators=(',',':'))+'\n',
                                          encoding='utf-8')


if __name__ == '__main__':
    main()
