const assert = require('node:assert/strict');
const {createRequire}=require('node:module');
const {readFile,writeFile,mkdir,mkdtemp,rm}=require('node:fs/promises');
const {tmpdir}=require('node:os');
const {join,dirname,resolve}=require('node:path');
const engine=resolve(__dirname,'../..');
const studio=join(engine,'studio');
const root=join(studio,'public','font-writing-test');
const output=process.env.FONT_TEST_STILLS;
const req=createRequire(join(studio,'package.json'));
const {bundle}=req('@remotion/bundler');
const {openBrowser,selectComposition}=req('@remotion/renderer');
const {NoReactInternals}=req('remotion/no-react');
const renderer=dirname(req.resolve('@remotion/renderer'));
const {prepareServer}=req(join(renderer,'prepare-server'));
const {setPropsAndEnv}=req(join(renderer,'set-props-and-env'));
const {seekToFrame}=req(join(renderer,'seek-to-frame'));
const props={videoId:'font-writing-test',timelineFile:'Motor_Test.json'};
const serialize=data=>NoReactInternals.serializeJSONWithSpecialTypes({data,staticBase:null}).serializedString;
const read=async name=>JSON.parse(await readFile(join(root,name),'utf8'));

(async()=>{
 const temp=await mkdtemp(join(tmpdir(),'three-body-qa-'));
 let browser,server;
 try {
  const spec=await read('Motor_Test.json');
  const framesTotal=Math.round(spec.duration*30);
  const url=await bundle({entryPoint:join(studio,'src/index.ts'),outDir:join(temp,'site'),publicDir:join(studio,'public'),symlinkPublicDir:true});
  server=await prepareServer({webpackConfigOrServeUrl:url,port:null,remotionRoot:studio,sampleRate:48000,logLevel:'error',indent:false});
  browser=await openBrowser('chrome',{browserExecutable:process.env.CHROME_PATH || null,logLevel:'error'});
  const comp=await selectComposition({id:'C',serveUrl:server.serveUrl,inputProps:props,puppeteerInstance:browser});
  assert.deepEqual([comp.width,comp.height,comp.fps,comp.durationInFrames],[1920,1080,30,framesTotal]);
  assert.equal(comp.props.error,null);
  const timeline=comp.props.timeline;
  assert.equal(timeline.scenes.length,9);
  assert(!timeline.audio);

  const page=await browser.newPage({context:()=>null,logLevel:'error',indent:false,pageIndex:0,onBrowserLog:null,onLog:()=>{}});
  await page.setViewport({width:1920,height:1080,deviceScaleFactor:1});
  const timeoutInMilliseconds=30000;
  await setPropsAndEnv({page,serveUrl:server.serveUrl,proxyPort:server.offthreadPort,
   serializedInputPropsWithCustomSchema:serialize(props),initialFrame:0,timeoutInMilliseconds,
   audioEnabled:false,videoEnabled:true,indent:false,logLevel:'error',onServeUrlVisited:()=>{},
   isMainTab:true,initialMemoryAvailable:1024**3,sampleRate:48000});
  await page.evaluate((composition, p)=>window.remotion_setBundleMode({type:'composition',
   compositionName:composition.id,serializedResolvedPropsWithSchema:p,compositionWidth:1920,
   compositionHeight:1080,compositionDurationInFrames:composition.durationInFrames,compositionFps:30}),comp,serialize(comp.props));
  const seek=frame=>seekToFrame({frame,page,composition:'C',timeoutInMilliseconds,logLevel:'error',
    indent:false,attempt:1});

  if(output) await mkdir(output,{recursive:true});
  const samples=[];
  const contacts=[];
  const paintedImages=[];
  for(const [i,scene] of timeline.scenes.entries()){
   const id=scene.id;
   const visualFrames=new Set([Math.ceil((scene.start+(id==='katex-formulas'?1.8:0))*30), Math.floor((scene.start+scene.end)/2*30),
     Math.round(scene.end*30)-(i===8?1:19)]);
   const frames=visualFrames;
   for(const frame of frames){
    await seek(frame);
    const state=await page.evaluate(id=>{
     const scene=document.querySelector(`[data-scene="${id}"]`);
     if(!scene)return null;
     return {
       hands:scene.querySelectorAll('[data-draw-hand],[data-carry-hand]').length,
       visible:[...scene.querySelectorAll('[data-el]')].filter(n=>Number(getComputedStyle(n).opacity)>0.001).length,
       emptyImages:[...scene.querySelectorAll('img')].filter(n=>n.complete&&n.naturalWidth===0).length
     };
    },id);
    assert(state&&state.hands<=1&&state.visible>0&&state.emptyImages===0,`${id} frame ${frame}: ${JSON.stringify(state)}`);
    if(output){
     const {value:{data}}=await page._client().send('Page.captureScreenshot',{format:'jpeg',quality:78});
     await writeFile(join(output,`${id}-${frame}.jpg`),Buffer.from(data,'base64'));
    }
    samples.push({scene:id,frame,...state});
   }
   if(id==='katex-formulas'){
    const tags=await page.evaluate(()=>[...document.querySelectorAll('[data-formula] math *')]
      .map(node=>node.localName));
    for(const tag of ['mfrac','msub','msup','msqrt','mover']) assert(tags.includes(tag),tag);
    assert.equal(await page.evaluate(()=>document.querySelectorAll('[data-formula] .katex').length),3);
   }
   if(scene.elements.some(e=>e.penPaint)) await seek(Math.round((scene.end-.55)*30));
   for(const image of scene.elements.filter(e=>e.penPaint)){
    const frame=Math.round((scene.end-.55)*30);
    const comparison=await page.evaluate(async id=>{
     const canvas=document.querySelector(`[data-el="${id}"] [data-painted-source]`);
     if(!canvas)return null;
     const ref=document.createElement('canvas');
     ref.width=canvas.width;ref.height=canvas.height;
     const ctx=ref.getContext('2d');
     const img=new Image();img.src=canvas.dataset.paintedSource;await img.decode();
     ctx.drawImage(img,0,0,ref.width,ref.height);
     const a=canvas.getContext('2d').getImageData(0,0,ref.width,ref.height).data;
     const b=ctx.getImageData(0,0,ref.width,ref.height).data;
     let different=0,alpha=0,max=0;
     for(let i=0;i<a.length;i+=4){
      const delta=Math.max(...[0,1,2,3].map(j=>Math.abs(a[i+j]-b[i+j])));
      if(delta){different++;max=Math.max(delta,max);}
      if(a[i+3]!==b[i+3])alpha++;
     }
     return {different,alpha,max};
    },image.id);
    assert(comparison,`missing painted image ${image.id} at ${frame}`);
    paintedImages.push({scene:id,image:image.id,frame,...comparison});
   }
   for(const stroke of scene.elements.filter(e=>e.hand).sort((a,b)=>b.enterDuration-a.enterDuration).slice(0,3)){
    const frame=Math.round((stroke.enterAt+stroke.enterDuration*.5)*30);
    await seek(frame);
    const row=await page.evaluate(({id,tip})=>{
     let p=document.querySelector(`[data-color-route="${id}"],[data-ink-route="${id}"]`);
     let painted=!!p;
     p??=document.querySelector(`[data-el="${id}"] path[stroke-dashoffset]`);
     const hand=document.querySelector('[data-draw-hand="stroke"]');
     if(!p||!hand)return null;
     const length=p.getTotalLength()-(painted?0:Number(p.getAttribute('stroke-dashoffset')));
     const point=p.getPointAtLength(length).matrixTransform(p.getScreenCTM());
     const rect=hand.getBoundingClientRect();
     return {x:rect.left+tip.x*rect.width/hand.naturalWidth,y:rect.top+tip.y*rect.height/hand.naturalHeight,
       targetX:point.x,targetY:point.y};
    },{id:stroke.id,tip:timeline.hand.tip});
    assert(row,`missing ${stroke.id} ${frame}`);
    const error=Math.hypot(row.x-row.targetX,row.y-row.targetY);
    assert(error<.12,`${stroke.id}: ${error}`);
    contacts.push({scene:id,stroke:stroke.id,frame,error});
   }
  }
  const unpainted=paintedImages.filter(x=>x.different>0);
  assert.deepEqual(unpainted,[]);
  const result={samples:samples.length,contacts:contacts.length,
    maxErrorPx:Math.max(...contacts.map(p=>p.error)),paintedImages:paintedImages.length,formulaCount:3};
  console.log(JSON.stringify(result));
 }finally{
  if(browser)await browser.close({silent:true});
  if(server)await server.closeServer(true);
  await rm(temp,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
