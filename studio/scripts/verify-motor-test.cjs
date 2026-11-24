#!/usr/bin/env node
const assert = require('node:assert/strict');
const {mkdir, mkdtemp, rm, writeFile} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const {dirname, join, resolve} = require('node:path');
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition} = require('@remotion/renderer');
const {NoReactInternals} = require('remotion/no-react');

// Use Remotion's frame-seek helper to inspect the same Chromium composition that is encoded.
const renderer = dirname(require.resolve('@remotion/renderer'));
const {prepareServer} = require(join(renderer, 'prepare-server'));
const {setPropsAndEnv} = require(join(renderer, 'set-props-and-env'));
const {seekToFrame} = require(join(renderer, 'seek-to-frame'));
const inputProps = {videoId: 'motor-demo', timelineFile: 'timeline.json'};
const out = resolve(process.argv[2] ?? 'out/motor-demo');
const browserExecutable = process.env.CHROME_PATH;
const timeoutInMilliseconds = 30000;
const serialize = (data) =>
	NoReactInternals.serializeJSONWithSpecialTypes({data, staticBase: null}).serializedString;
const near = (actual, expected, limit = .06) => assert(Math.abs(actual - expected) < limit, `${actual} vs. ${expected}`);

async function main() {
	const tmp = await mkdtemp(join(tmpdir(), 'full-animation-qa-'));
	let browser;
	let server;
	try {
		await mkdir(out, {recursive: true});
		const serveUrl = await bundle({entryPoint: resolve('src/index.ts'), outDir: tmp, symlinkPublicDir: true});
		server = await prepareServer({webpackConfigOrServeUrl: serveUrl, port: null, remotionRoot: resolve('.'),
			sampleRate: 48000, logLevel: 'error', indent: false});
		browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
		const comp = await selectComposition({id: 'C', serveUrl: server.serveUrl, inputProps, puppeteerInstance: browser});
		assert.deepEqual([comp.width, comp.height, comp.fps, comp.durationInFrames], [1920, 1080, 30, comp.props.timeline.duration * 30]);
		const timeline = comp.props.timeline;
		const tips = {pen: timeline.hand.tip, finger: timeline.carryHand.tip};
		const page = await browser.newPage({context: () => null, logLevel: 'error', indent: false,
			pageIndex: 0, onBrowserLog: null, onLog: () => {}});
		await page.setViewport({width: comp.width, height: comp.height, deviceScaleFactor: 1});
		await setPropsAndEnv({page, serveUrl: server.serveUrl, proxyPort: server.offthreadPort,
			serializedInputPropsWithCustomSchema: serialize(inputProps), initialFrame: 0, timeoutInMilliseconds,
			audioEnabled: false, videoEnabled: true, indent: false, logLevel: 'error', onServeUrlVisited: () => {},
			isMainTab: true, initialMemoryAvailable: 1024 ** 3, sampleRate: 48000});
		await page.evaluate((composition, props) => window.remotion_setBundleMode({
			type: 'composition', compositionName: composition.id, serializedResolvedPropsWithSchema: props,
			compositionWidth: composition.width, compositionHeight: composition.height,
			compositionDurationInFrames: composition.durationInFrames, compositionFps: composition.fps,
		}), comp, serialize(comp.props));
		assert.equal(timeline.scenes.length, 31);
		const seek = (frame) => seekToFrame({frame, page, composition:'C', timeoutInMilliseconds,
			logLevel:'error', indent:false, attempt:1});
		const at = async (frame, contact = null) => {
			await seek(frame);
			return page.evaluate(({pen,finger}, grip) => {
				const wrap = document.querySelector('[data-carry-hand]');
				const drawing = document.querySelector('[data-draw-hand]');
				const image = wrap?.querySelector('img') ?? drawing;
				const phase = wrap?.dataset.carryHand ?? drawing?.dataset.drawHand ?? '';
				const active = document.querySelectorAll('[data-el^="ink-"] path[stroke-dashoffset]');
				const reveal = document.querySelector('[data-reveal-front]');
				const container = grip ? document.querySelector(`[data-el="${grip.id}"]`) : null;
				const mark = (el, point) => {
					const n = document.createElement('span');
					Object.assign(n.style,{position:'absolute',width:'0px',height:'0px',left:point.x+'px',top:point.y+'px'});
					el.append(n);
					const b=n.getBoundingClientRect();
					n.remove();
					return [b.left,b.top];
				};
				let target = null, tip = null;
				if (active.length === 1) {
					const p=active[0];
					const q=p.getPointAtLength(p.getTotalLength()-Number(p.getAttribute('stroke-dashoffset')))
						.matrixTransform(p.getScreenCTM());
					target = [q.x,q.y];
				} else if (reveal && phase==='stroke') {
					const [x,y]=reveal.dataset.revealFront.split(',').map(Number);
					const b=reveal.getBoundingClientRect();
					target=[b.left+x*b.width,b.top+y*b.height];
				} else if (container && ['grip','carry','release'].includes(phase)) {
					target=mark(container,grip.local);
				}
				if (image && target) {
					const b=image.getBoundingClientRect();
					const loc=wrap ? finger : pen;
					tip=[b.left+loc.x*b.width/image.naturalWidth,b.top+loc.y*b.height/image.naturalHeight];
				}
				return {phase,tip,target,active:active.length,
					hands:document.querySelectorAll('[data-draw-hand],[data-carry-hand]').length,
					scene:[...document.querySelectorAll('[data-scene]')].map(n=>{
						const b=n.getBoundingClientRect();
						return [n.dataset.scene,b.left,b.right,getComputedStyle(n).overflow];
					}),
					center:container?mark(container,{x:0,y:0}):null,
					backgroundBehind: container ? !container.previousElementSibling : false,
					formula:[...document.querySelectorAll('[data-formula]')].map(n=>[n.dataset.formula,
						n.querySelector('math')?.innerHTML ?? '',n.getBoundingClientRect().width])};
			}, tips, contact);
		};
		const records=['frame,time_s,scene,phase,tip_x,tip_y,target_x,target_y,error_px'];
		const contactStats={};
		const formulae = new Set();
		let seams=0, penUp=0;
		for(const [i,scene] of timeline.scenes.entries()) {
			const car=scene.elements.find(e=>e.carry);
			const f0=Math.round(scene.start*30), f1=Math.round(scene.end*30);
			const grip=car ? {id:car.id,local:car.carry.grip} : null;
			if (car?.role==='background') {
				const init=await at(f0,grip);
				assert.deepEqual(init.center,[car.x,car.y]);
				assert(init.backgroundBehind,scene.id);
				for(const t of [car.carry.land+.1, car.carry.end+.4, scene.end-1.2]){
					const settled=await at(Math.ceil(t*30),grip);
					settled.center.forEach((n,axis)=>near(n,axis?car.carry.target.y:car.carry.target.x));
					assert(settled.backgroundBehind);
				}
			}
			const sampleFrames=new Set([f0+Math.round((f1-f0)*.45),f1-32]);
			if(scene.penTravel) {
				for(let f=Math.ceil(scene.penTravel.start*30);f<scene.penTravel.end*30;f+=3) sampleFrames.add(f);
			}
			if(car) for(let f=Math.ceil(car.carry.contact*30);f<car.carry.release*30;f+=2) sampleFrames.add(f);
			for(const f of [...sampleFrames].sort((a,b)=>a-b)){
				const row=await at(f,grip);
				assert(row.hands<=1 && row.active<=1,`overlap ${scene.id} ${f}`);
				if(row.phase==='travel'){assert.equal(row.active,0);penUp++;}
				if(row.tip&&row.target){
					const d=Math.hypot(row.tip[0]-row.target[0],row.tip[1]-row.target[1]);
					assert(d<.1,`contact at ${scene.id} ${f}: ${d}`);
					const stat=contactStats[scene.id]??={count:0,maxPx:0};
					stat.count++;stat.maxPx=Math.max(d,stat.maxPx);
					records.push([f,f/30,scene.id,row.phase,...row.tip,...row.target,d].join(','));
				}
				for(const [source,ml,width] of row.formula){
					assert(ml.length>20&&width>10,source);
					formulae.add(source);
				}
			}
			if(i<timeline.scenes.length-1){
				for(const f of [f1-18,f1-10,f1-3]){
					const row=await at(f);
					assert.equal(row.hands,0);assert.equal(row.scene.length,2);
					near(row.scene[0][2],row.scene[1][1]);
					assert(row.scene.every(s=>s[3]==='hidden'));
					seams++;
				}
			}
		}
		for(const scene of ['background','handwriting','layers','bg-two','highlight','svg','full-one','full-two','reveal'])
			assert(contactStats[scene]?.count>14,scene);
		assert(formulae.size>=16,formulae.size);
		const draft=timeline.scenes.find(s=>s.id==='reassemble');
		const screenshot=async t=>{
			await seek(Math.round(t*30));
			const {value:{data}}=await page._client().send('Page.captureScreenshot',{format:'png'});
			assert(typeof data==='string'&&data.length>100);
			return data;
		};
		assert.equal(await screenshot(draft.start+.5),await screenshot(draft.end-.8),'reassembled raster differs');
		const required=['draw','slide','rotate','grow','fade','morph','zoom','scatter','reassemble','transform','layers','bg-two','audio','explainer'];
		assert(required.every(id=>timeline.scenes.some(s=>s.id===id)));
		const json={contactStats,penUpSamples:penUp,transitionSamples:seams,formulaVariants:formulae.size,
			effectsPresent:required,pixelReassembly:true};
		await writeFile(join(out,'coordinates.csv'),records.join('\n')+'\n');
		await writeFile(join(out,'browser.json'),JSON.stringify(json,null,2)+'\n');
		console.log(JSON.stringify(json));

	} finally {
		await browser?.close({silent: true});
		await server?.closeServer();
		await rm(tmp, {recursive: true, force: true});
	}
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
