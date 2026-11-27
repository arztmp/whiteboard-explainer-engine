"""Compile native KaTeX elements with scene-local timing."""
import json
from math import isfinite
import subprocess


def formula_element(id_, latex, *, x, y, size, color, start, duration):
    if not isinstance(latex,str) or not latex.strip():
        raise ValueError(f'{id_}: LaTeX must be a nonempty string')
    if not all(isfinite(v) for v in (x,y,size,start,duration)) or size<=0 or start<0 or duration<0:
        raise ValueError(f'{id_}: invalid position, size or timing')
    return dict(id=id_,type='formula',latex=latex,x=x,y=y,size=size,color=color,
                enter='fade' if duration else 'none',enterAt=start,enterDuration=duration)


def validate_formulas(scenes, studio):
    """Check authored LaTeX with the same local KaTeX version before publishing the plan."""
    payload = [(e['id'], e['latex']) for s in scenes for e in s.get('elements',()) if e['type']=='formula']
    if not payload:
        return
    code = """
const katex = require('katex');
const entries = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
for (const [id, latex] of entries) {
    try {
        if (typeof latex !== 'string' || !latex.trim()) throw new Error('LaTeX must be a nonempty string');
        katex.renderToString(latex, {throwOnError: true, trust: false, maxExpand: 1000, strict: code => code === 'unknownSymbol' ? 'error' : 'warn'});
    } catch (error) {
        console.error(id + ': ' + error.message);
        process.exitCode = 1;
    }
}
"""
    result = subprocess.run(['node','-e',code],input=json.dumps(payload),text=True,capture_output=True,cwd=studio)
    if result.returncode:
        raise ValueError(f'Invalid KaTeX formulas:\n{result.stderr.strip()}')
