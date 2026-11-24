"""Compile the English science acceptance film from source images and reusable motion plans."""
import hashlib
import json
import math
import os
import re
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.handwriting import handwriting
from engine.illustration import analyze, compile_illustration
from engine.scientific import formula_strokes
from engine.stroke_plan import THEME as P, pen_window, polyline, schedule

PUBLIC = ROOT / "studio/public"
OUT = PUBLIC / "motor-demo"
FILES = {int(p.name[1:3]): p for p in OUT.glob("S*.png")}
assert set(FILES) == {2, 9, 11, 13, 17, 20, 29, 30, 32}
SIZE = {n: Image.open(p).size for n, p in FILES.items()}
N, O, C, R, G, W, B = (P[k] for k in ("navy","orange","cyan","red","gray","white","cream"))
scenes, coverage, words, formula_ids = [], [], [], []
clock = 0
chrome = os.environ.get("CHROME_PATH", "/usr/bin/chromium")
original = json.loads((PUBLIC / "hand-motion-demo/timeline.json").read_text())


def v(x,y):
    return dict(x=x,y=y)


def text(id_, value, x, y, size=31, color=N, **kw):
    return dict(id=id_, type="text", mode="typography", text=value, x=x, y=y, size=size, color=color,
                **({"weight": 600, "font": "sans", "enter": "none", "letterSpacing": .4} | kw))


def rect(id_, x,y,w,h,fill, **kw):
    return dict(id=id_, type="rect", x=x,y=y,w=w,h=h,fill=fill,enter="none",stroke="none", **kw)


def picture(id_, source, x,y,w, **kw):
    return dict(id=id_, type="image", src=FILES[source].name, x=x,y=y,w=w, **({"enter":"none"} | kw))


def math_display(id_, latex, x,y,size=48, **kw):
    formula_ids.append(id_)
    return dict(id=id_,type="formula",latex=latex,x=x,y=y,size=size, **({"enter":"fade","enterAt":clock+.4,"enterDuration":.7} | kw))


def add(id_, title, dur, content, *, pen=None, white=False, camera=None):
    global clock
    h = [rect(f"{id_}-title-panel", 960,105,1550,120,B,radius=20,z=20,screenFixed=True),
         text(f"{id_}-title", title,960,105,48,z=21,screenFixed=True)]
    items = h + list(content)
    # Use scene-qualified IDs to keep source plans reusable.
    for e in items:
        if not e["id"].startswith("ink-"):
            e["id"] = f"{id_}:{e['id']}"
    scene = dict(id=id_,start=clock,end=clock+dur,background=W if white else B,elements=items,
                 transitionIn=dict(type="push-left",duration=.75))
    if pen is not None:
        scene["penTravel"] = pen_window(clock+pen,clock+dur-.91,scale=.68)
    if camera:
        scene["camera"] = camera
    scenes.append(scene)
    clock += dur


def drag(id_, source, direction, *, target=(960,540), w=1920, h=None, start=.18, land=5.4,
         finish=6.6, background=False, fit="contain", after=None):
    iw,ih=SIZE[source]
    h = w*ih/iw if h is None else h
    x,y=target
    options = {
        "left": ((-w/2-24,y),(w/2-8,0),(-700,y+80),(2100,1320)),
        "right": ((1920+w/2+24,y),(-w/2+8,0),(2380,y+80),(400,1350)),
        "top": ((x,-h/2-24),(0,h/2-8),(x+200,-620),(1450,1370)),
        "bottom": ((x,1080+h/2+24),(0,-h/2+8),(x+140,1450),(2000,1370)),
    }
    (sx,sy),grip,origin,exit_ = options[direction]
    if not background:
        with Image.open(FILES[source]) as original:
            alpha=np.asarray(original.convert("RGBA").getchannel("A"))
            if direction in {"left","right"}:
                edge=np.flatnonzero(alpha[ih//2]>128)
                idx=edge[-1] if direction=="left" else edge[0]
                grip=((idx/iw-.5)*w + (-3 if direction=="left" else 3),0)
            else:
                edge=np.flatnonzero(alpha[:,iw//2]>128)
                idx=edge[-1] if direction=="top" else edge[0]
                grip=(0,(idx/ih-.5)*h + (-3 if direction=="top" else 3))
    plan = dict(mode="drag",grip=v(*grip),target=v(x,y),start=clock+start,contact=clock+start+.8,
                pickup=clock+start+1,land=clock+land,release=clock+land+.16,end=clock+finish,
                **{"from":v(*origin),"to":v(*exit_)})
    if after:
        plan["after"]=after
    return picture(id_,source,sx,sy,w,h=h,fitImage=fit,carry=plan,**({"role":"background"} if background else {}))


def write(id_,value,x,y,size,first,last, **kw):
    strokes,_=handwriting(value,x,y,size, **kw)
    return schedule(strokes,clock+first,clock+last,f"ink-{id_}")


def plot(id_, paths, first, last, color=N, width=4):
    return schedule([polyline(p,width,color=color) for p in paths],clock+first,clock+last,f"ink-{id_}")


def loop(x,y,rx,ry,start=0,end=math.tau,n=54):
    return [(x+rx*math.cos(start+(end-start)*i/n),y+ry*math.sin(start+(end-start)*i/n)) for i in range(n+1)]


def arrow(x,y,xx,yy):
    a=math.atan2(yy-y,xx-x)
    return [(x,y),(xx,yy)],[(xx-22*math.cos(a-.55),yy-22*math.sin(a-.55)),(xx,yy),
                           (xx-22*math.cos(a+.55),yy-22*math.sin(a+.55))]


def diagram(prefix,first,last, y=580, motion=None):
    pts=[(495,y-85),(970,y+105),(1440,y-65)]
    routes=[loop(960,y+8,585,235,.2,math.tau+.2)]
    for x,py in pts: routes.append(loop(x,py,45,45))
    for (x,py),(xx,yy) in zip(pts,pts[1:]):
        routes.extend(arrow(x+53,py,xx-53,yy))
    routes += [[(530,y-244),(1390,y-244)],[(530,y-259),(530,y-229)],[(1390,y-259),(1390,y-229)]]
    result=plot(prefix,routes,first,last)
    if motion:
        for stroke in result[1:]:
            stroke["inkFade"] = dict(at=clock+21.7,end=clock+22.16)
    for i,(x,yy) in enumerate(pts):
        body = dict(id=f"{prefix}-body-{i}",type="circle",x=x,y=yy,r=40,fill=(O,C,R)[i],
                    enter="fade", enterAt=clock+first+(last-first)*.53,enterDuration=.85,z=-1)
        if motion:
            tx,ty,px,py=motion[i]
            body["moves"]=[dict(at=clock+22.25,duration=5.8,x=tx,y=ty,via=v(px,py))]
        result.append(body)
    options = {"exit": "fade", "exitAt": clock+21.7, "exitDuration": .46} if motion else {}
    result.append(text(f"{prefix}-distance","Separation r",960,y-270,24,enter="fade",enterAt=clock+last-.4,**options))
    return result


add("background","Background placement",12,[
    drag("bg",2,"left",background=True),text("note","A landscape is pushed onto the board",960,925,30,N,
    box="card",boxColor=B,enter="fade",enterAt=clock+7)],white=True)
add("handwriting","Handwriting · A scientific title",19,[
    drag("bg",2,"right",background=True,land=4.5,finish=5.55),
    rect("board",960,550,1510,460,B,enterAt=clock+5.5),
    *write("title","THE THREE-BODY PROBLEM",310,510,69,6.55,11.95,width=5.8,tracking=7,max_width=1320),
    *write("gravity","Gravity shapes the universe.",430,731,75,12.76,17.82,width=4.6),
],pen=5.58,white=True)
add("typography","Typography",7,[
    text("topic","Mass, distance and gravitational force",960,330,64,weight=800),
    text("subtitle","The same rules govern planets, stars and satellites",960,464,34,O),
    text("body","Initial conditions determine the evolution of the system.",720,680,36,
         weight=400,maxWidth=650,lineHeight=1.5,enter="slide",enterOffset=v(-180,0),enterAt=clock+1),
    picture("galaxy",30,1510,680,335,enter="fade",enterAt=clock+1.6),
],white=True)
add("multiline","Multiline writing",24,[
    *write("multiline","Small changes can produce dramatically different outcomes.",280,478,80,1,19.1,
           width=4.8,max_width=1260,line_height=1.5),
    *write("units","3 bodies. 2 m apart.",380,845,65,20.05,22.85,color=N,width=4.3),
],pen=.10)
basic=[]
for i,(visible,latex) in enumerate([("2 + 3 = 5","2+3=5"),("8 - 3 = 5","8-3=5"),("2 × 4 = 8",r"2\times 4=8"),("8 ÷ 2 = 4",r"8\div 2=4")]):
    basic.append(math_display("operation-"+str(i),latex,490+950*(i%2),400+380*(i//2),47))
basic += write("basic","2 + 3 = 5",470,625,99,1.2,9.9,width=5,color=O)
add("basic-math","Basic mathematics · Display and pen",12,basic,pen=.1)
add("scientific","Scientific formulas",9,[
    math_display("einstein",r"E=mc^2",495,385,61),
    math_display("newton",r"F=ma",495,590,61,enter="slide",enterOffset=v(-400,0),enterAt=clock+1.1),
    math_display("gravity",r"F=G\frac{m_1m_2}{r^2}",505,818,57,enter="grow",enterAt=clock+2.2,enterDuration=1.1),
    picture("newton-portrait",9,1355,615,680,enter="fade",enterAt=clock+.6),
],white=True)
advanced=[
    r"a^2+b^2=c^2",r"x=\sqrt{a^2+b^2}",r"v=\frac{\Delta x}{\Delta t}", r"E_k=\frac12 mv^2",
    r"\omega=\frac{2\pi}{T}",r"G\approx 6.674\times10^{-11}\;\mathrm{N\!\cdot m^2/kg^2}",
    r"\sum_{i=1}^{n}m_i",r"\int_0^1x^2\,dx=\frac13",
    r"\ddot{\mathbf r}_i=G\sum_{j\ne i}m_j\frac{\mathbf r_j-\mathbf r_i}{\|\mathbf r_j-\mathbf r_i\|^3}",
    r"\left[\frac{1}{1+\frac12}\right] < |x|\leq\infty",
]
add("advanced","Advanced mathematical layout",11,[
    math_display(f"advanced-{i}",latex,520+880*(i%2),285+155*(i//2),39 if i in {5,8,9} else 49,
                 enterAt=clock+.45+i*.47,enterDuration=.5)
    for i,latex in enumerate(advanced)])
force=("row","F","=","G",("fraction",("row",("sub","m","1"),("sub","m","2")),("sup","r","2")))
add("highlight","Formula writing and highlighting",13,[
    *schedule(formula_strokes(force,315,540,100,color=N),clock+1.2,clock+7.85,"ink-force"),
    math_display("color-formula",r"F=\textcolor{#E88728}{G}\frac{m_1m_2}{\textcolor{#D90000}{r^2}}",
                 490,880,52,enterAt=clock+8.5),
    picture("portrait",9,1370,610,600),text("explanation","Force decreases with squared distance",1120,932,32,
                maxWidth=760,enter="fade",enterAt=clock+8.4),
    *plot("underline", [[(320,695),(780,695)],loop(626,522,51,67),*arrow(800,570,1120,520)],8.48,11.82,O),
],pen=.1,white=True)
add("geometry","Geometry · Shapes and arrows",12,plot("geometry",[
    loop(405,386,92,92),loop(808,386,133,79),[(1090,300),(1270,300),(1270,480),(1090,480),(1090,300)],
    [(1390,312),(1640,312),(1640,480),(1390,480),(1390,312)],[(310,804),(432,590),(555,804),(310,804)],
    loop(780,706,115,105,0,math.tau,6),[(960,655),(1130,655)],loop(1240,760,130,108,math.pi,math.tau),[(1352,725),(1370,760),(1390,730)],
    *[[(1380+i*36,680),(1396+i*36,680)] for i in range(7)],*arrow(340,923,660,923),
    *arrow(905,923,1190,923),*arrow(1190,923,905,923),
],.9,10.65),pen=.1)
add("diagram","Scientific diagram · Three interacting bodies",15,diagram("diagram",1.1,13.7),pen=.1,white=True)
graph=[*arrow(265,795,265,310),*arrow(265,795,1010,795),
       [(275+i*14,742-.88*i-0.12*i*i) for i in range(48)],
       [(1160,835),(1160,325)],[(1160,835),(1630,835)],[(1170,697),(1310,570),(1455,661),(1590,445)]]
for idx,height in enumerate((90,160,230)):
    x=550+idx*95
    graph.append([(x,950),(x,950-height*.42),(x+55,950-height*.42),(x+55,950)])
add("graphs","Coordinate axes, function and data graphs",14,plot("graphs",graph,1,12.4)+[
    text("x", "X",1055,796,26),text("y","Y",264,282,26),
    text("curve","Function and bars",540,250,34),
    text("line","Sample observations",1400,250,34)],pen=.1)

for name,source,duration,mode,width in (("trace",17,15,"trace",895),("full-one",9,18,"full",660),("full-two",11,19,"full",980)):
    if name=="full-one":
        reveal=picture("image",30,960,622,650,enter="draw",enterAt=clock+1,
                       enterDuration=6.5, hand=True,reveal={"rows":6})
        add("reveal","PNG reveal · Spiral galaxy",9,[reveal],pen=.1,white=True)
    profile=analyze(FILES[source],chrome,resolution=470 if source==11 else 410,connect=True)
    el,report=compile_illustration(profile,FILES[source].name,f"ink-{name}", (960,625),width,
                                   clock+1,clock+duration-1.8,mode=mode,limit=None,allow_trace=True)
    coverage.append(report)
    add(name,{"trace":"PNG TRACE · Butterfly","full-one":"Full illustration draw · Isaac Newton",
              "full-two":"Full illustration draw II · Webb telescope"}[name],duration,el,pen=.1,white=name!="trace")
geometry=PUBLIC/"professional-draw/geometry.svg"
el,report=compile_illustration(analyze(geometry,chrome),"/professional-draw/geometry.svg","ink-svg",
                                  (960,575),1350,clock+1,clock+8.55,mode="full")
coverage.append(report)
add("svg","SVG drawing · Native geometry and fills",10,el,pen=.1)
add("drag","Hand drag · Surface contact",9,[
    drag("drag-item",29,"left",target=(1090,610),w=630,land=4.8,finish=6.2,
         after=[dict(at=clock+6.45,duration=1.55,x=1400,y=600,scale=.68)]),
    text("drag-label","Hand contact, release, then independent motion",960,940,27)])
img=picture("image",17,960,600,880,enter="draw",enterAt=clock+1,enterDuration=6.35, hand=True,reveal={"rows":5})
add("draw","DRAW entrance",9,[img],pen=.1,white=True)
add("slide","SLIDE entrance · Four directions",8,[
    picture(f"slide-{i}",source,420+(i%2)*1060,390+(i//2)*420,340,enter="slide",
            enterAt=clock+.5+i*.9,enterDuration=1.5,enterOffset=v(*offset))
    for i,(source,offset) in enumerate(zip((9,11,13,29),((-850,0),(900,0),(0,-1100),(0,650))))
])
add("rotate","ROTATE entrance · Both directions",7,[
    picture("cw",29,600,590,560,enter="rotate",enterAt=clock+.8,enterDuration=3,enterAngle=-260),
    picture("ccw",30,1320,590,550,enter="rotate",enterAt=clock+.8,enterDuration=3,enterAngle=260)])
add("grow","GROW · Centre and anchored pivot",7,[
    picture("center",30,570,605,550,enter="grow",enterAt=clock+.6,enterDuration=3,enterScale=.05),
    picture("pivot",11,1320,605,650,enter="grow",enterAt=clock+.6,enterDuration=3,enterScale=.05,
            growOrigin=v(-290,190))],white=True)
add("fade","FADE IN / FADE OUT",8,[
    picture("fade-item",13,960,610,665,enter="fade",enterAt=clock+.8,enterDuration=2.05,
            exit="fade",exitAt=clock+4.3,exitDuration=2.8,enterCurve="ease-in-out",exitCurve="linear")])
# Reuse the existing contour morph planner on the new source assets.
def silhouette(number, size=520):
    from scipy import ndimage
    from skimage import measure
    with Image.open(FILES[number]) as source:
        alpha=source.convert("RGBA").getchannel("A")
        alpha.thumbnail((500,500))
    mask=np.asarray(alpha)>=100
    labels,_=ndimage.label(mask)
    counts=np.bincount(labels.ravel());counts[0]=0
    ring=max(measure.find_contours(np.pad(labels==counts.argmax(),1),.5),key=len)[:-1,::-1]
    lo,hi=ring.min(axis=0),ring.max(axis=0)
    i=np.linalg.norm(ring-((hi[0]+lo[0])/2,lo[1]),axis=1).argmin()
    ring=np.roll(ring,-i,axis=0)
    ring=np.vstack((ring,ring[0]))
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(ring,axis=0),axis=1))]
    points=np.linspace(0,arc[-1],160,endpoint=False)
    return [v(x,y) for x,y in zip(*[(np.interp(points,arc,ring[:,i])-(hi[i]+lo[i])/2)*size/max(hi-lo) for i in (0,1)])]
add("morph","MORPH · Silhouette and colour",10,[
    picture("from-ref",17,392,605,410),picture("to-ref",30,1510,605,400),
    dict(id="shape",type="morph",x=960,y=605,at=clock+1.3,duration=7,enter="none",
         fill=O,toFill=N,**{"from":silhouette(17),"to":silhouette(30)})])
add("zoom","ZOOM IN / OUT · Object and camera",10,[
    picture("object",29,590,595,590,zoom={"at":clock+.8,"in":1.25,"hold":.7,"out":1.25,"scale":1.42,"origin":v(-82,66)}),
    picture("camera-target",11,1330,600,580),text("guide","Clockwork detail                 Telescope region",960,947,27),
],white=True,camera=[dict(at=clock+4.7,x=960,y=540,scale=1),dict(at=clock+6.7,x=1280,y=586,scale=1.42),
                     dict(at=clock+7.3,x=1280,y=586,scale=1.42),dict(at=clock+9,x=960,y=540,scale=1)])
for phase in ("scatter","reassemble"):
    effect=dict(at=clock+1.1 if phase=="scatter" else clock+1,out=2.5 if phase=="scatter" else .28,
                hold=2.45 if phase=="scatter" else 1.1,back=2.05 if phase=="scatter" else 3.6,
                columns=14,rows=10,rotation=105,fade=.18,direction=v(25,-80))
    add(phase,"PIXEL SCATTER" if phase=="scatter" else "PIXEL REASSEMBLE",9 if phase=="scatter" else 7,[
        picture("tiles",11,960,615,790,scatter=effect)])
add("transform","Object transformations",10,[
    picture("orbital",30,460,650,515,moves=[dict(at=clock+1.0,duration=3,x=1350,y=480,via=v(900,260),rotate=37,scale=1.22,z=2),
         dict(at=clock+4.4,duration=2.0,x=900,y=739,scale=.67,rotate=-20,z=0),
         dict(at=clock+7.1,duration=1.9,x=2190,y=600,opacity=0)]),
    picture("secondary",17,1450,660,480,moves=[dict(at=clock+1.8,duration=3,x=710,y=600,scale=.81,z=1),
        dict(at=clock+5.3,duration=1.5,y=815,rotate=25)]),
],white=True)
add("layers","Layer management · Sky, objects and equations",12,[
    drag("bg",2,"top",background=True,target=(960,610),w=1850,h=900,fit="cover",land=4.4,finish=5.6),
    rect("plate",750,590,750,400,B,enterAt=clock+5.8,z=3),
    picture("telescope",11,1440,610,615,enter="grow",enterAt=clock+6,enterDuration=1.2),
    math_display("equation",r"F=G\frac{m_1m_2}{r^2}",750,588,56,enterAt=clock+6.4,z=4),
],white=True)
add("bg-two","Second background placement · From below",12,[
    drag("bg",20,"bottom",background=True,land=5.2,finish=6.5),
    rect("plate",830,505,1020,350,B,enterAt=clock+6.6),
    picture("portrait",13,1090,550,305,enter="fade",enterAt=clock+7),
    *write("bg-note","A second world.",460,530,68,7.1,10.8),
],pen=6.55,white=True)
# Synthetic cues use one external wave file, with timed entries on the same frame grid as the animation.
for name, offset in [("Gravity",1.4),("Three massive objects",4.0),("Interact",7.4),("Motion",9.8)]:
    words.append(dict(text=name,start=clock+offset,end=clock+offset+.6))
add("audio","Audio synchronization · Synthetic cue test",12,[
    dict(id="captions",type="caption",x=960,y=455,maxWidth=1600,size=57,words=words,
         activeColor=C,activeScale=1.12,bg=N,enter="none"),
    *[text(f"cue-{i}",word["text"],420+i*360,745,31,enter="grow",enterAt=word["start"],enterDuration=.48)
      for i,word in enumerate(words)]
],white=True)
add("explainer","Why three bodies are hard to predict",38,[
    rect("panel",960,300,1550,179,W,z=-2),
    text("opening","Two bodies can trace a regular orbit. Add a third and each path changes with the others.",
         960,304,37,weight=400,maxWidth=1410,lineHeight=1.45,enter="fade",enterAt=clock+.55),
    *diagram("explain",3,19,y=650, motion=[
        (1160,450,725,304),(1320,555,1470,870),(480,820,885,920)]),
    text("motion-note","Illustrative trajectories",960,382,24,weight=400,
         enter="fade",enterAt=clock+22.2,exit="fade",exitAt=clock+29,exitDuration=.45),
    math_display("acceleration",r"\ddot{\mathbf r}_i=G\sum_{j\ne i}m_j\frac{\mathbf r_j-\mathbf r_i}{\|\mathbf r_j-\mathbf r_i\|^3}",
                 920,955,46,enterAt=clock+18.7,enterDuration=.8,exit="fade",exitAt=clock+29.5,exitDuration=.8),
    text("bridge","Each acceleration combines pulls from the other bodies.",960,1041,23,
         enter="fade",enterAt=clock+20,exit="fade",exitAt=clock+29,exitDuration=.8),
    picture("poincare",13,1280,617,450,enter="fade",enterAt=clock+30,enterDuration=1.15,z=10),
    rect("closing-panel",650,612,920,440,B,enterAt=clock+29.9,z=9,radius=22),
    text("closing","Tiny changes in starting position can produce very different futures.",
         650,600,42,maxWidth=805,lineHeight=1.5,enter="fade",enterAt=clock+30.3,z=10),
],pen=.1,white=True)
# Exit the last pen as soon as the diagram ends.
scenes[-1]["penTravel"]["end"]=scenes[-1]["start"]+20.4
rate=48000
time=np.arange(round(.24*rate))/rate
tone=(np.sin(2*math.pi*630*time)*np.clip(time*150,0,1)*np.clip((.24-time)*150,0,1)*15000).astype("<i2")
with wave.open(str(OUT/"cue.wav"),"wb") as dest:
    dest.setparams((1,2,rate,len(tone),"NONE","not compressed"));dest.writeframes(tone.tobytes())
metadata=dict(allowMorph=True,allowLegacyBackgroundPlacement=True,style="B",width=1920,height=1080,fps=30,duration=clock,theme="brand",font="sans",sceneSlideLeft=True,
              scenes=scenes,hand=dict(original["hand"],src="/hand-motion-demo/Kalem_El.png"),
              carryHand=dict(original["carryHand"],src="/hand-motion-demo/El.png"),
              sfx=[dict(src="cue.wav",at=w["start"],volume=.7) for w in words])
assets=[dict(file=p.name,dimensions=SIZE[n],sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
             role="background" if n in {2,20,32} else "foreground",
             usage="Duplicate of S20" if n==32 else [
                 sc["id"] for sc in scenes if any(el.get("src")==p.name for el in sc["elements"])]) for n,p in sorted(FILES.items())]
(OUT/"timeline.json").write_text(json.dumps(metadata,ensure_ascii=False,separators=(",",":"))+"\n")
(OUT/"report.json").write_text(json.dumps(dict(duration=clock,cues=words,assets=assets,coverage=coverage,
                                            scenes=[dict(id=s["id"],start=s["start"],end=s["end"]) for s in scenes],
                                            formulaIds=formula_ids),indent=2)+"\n")
