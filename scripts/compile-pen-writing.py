"""Compile optional scene writing blocks from JSON using the native renderer."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from engine.formula_plan import formula_element, validate_formulas
from engine.font_pen import FontPen, pen_writing
from engine.stroke_plan import THEME


def compile_writing(timeline, output, font_dir):
    fonts = {}
    for scene in timeline['scenes']:
        elements = scene.setdefault('elements',[])
        for i,row in enumerate(scene.pop('formulas',[])):
            start = scene['start']+row.get('offset',0)
            duration = row.get('duration',0)
            if start < scene['start'] or start+duration > scene['end']:
                raise ValueError(f"{scene['id']}: formula timing must fit inside the scene")
            elements.append(formula_element(f"{scene['id']}-formula-{i}",row['latex'],
                x=row['x'],y=row['y'],size=row['size'],color=row.get('color',THEME['navy']),
                start=start,duration=duration))
        if 'writing' not in scene:
            continue
        if scene.get('penTravel') or any(e.get('hand') for e in scene.get('elements',())):
            raise ValueError(f"{scene['id']}: writing requires the scene's pen")
        if timeline['style'] == 'A' or not timeline.get('hand') or timeline.get('rough'):
            raise ValueError('Writing requires a calibrated hand, style B/C and ordinary path geometry')
        writing = scene.pop('writing')
        rows = []
        for row in writing['rows']:
            face = (600 if row.get('role')=='title' else 400,row.get('color',THEME['navy']))
            if face not in fonts:
                fonts[face] = FontPen.be_vietnam(font_dir,weight=face[0],color=face[1])
            rows.append((row['content'],row['x'],row['baseline'],row['size'],fonts[face]))
        if not rows:
            raise ValueError(f"{scene['id']}: writing.rows is empty")
        start = scene['start']+writing.get('offset',1.0)
        span = writing['duration']
        speed = writing.get('speed',1)
        if speed<=0 or start-.65<scene['start'] or start+span/speed+.65>scene['end']:
            raise ValueError(f"{scene['id']}: writing and pen travel must fit inside the scene")
        ink,travel = pen_writing(rows[0][-1],rows,asset_dir=output.parent/'writing-glyphs',
            asset_prefix='writing-glyphs',id_prefix=scene['id']+'-writing',start=start,end=start+span,
            speed=speed,hand_scale=writing.get('handScale',.55),canvas=(timeline['width'],timeline['height']))
        elements.extend(ink)
        scene['penTravel'] = travel
    validate_formulas(timeline['scenes'],ROOT/'studio')
    return timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--font-dir',type=Path,
        default=ROOT/'studio/node_modules/@fontsource/be-vietnam-pro/files')
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():
        parser.error('Choose separate source and output paths.')
    plan=compile_writing(json.loads(args.input.read_text(encoding='utf-8')),args.output,args.font_dir)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
