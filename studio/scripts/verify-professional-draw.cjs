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
const inputProps = {videoId: 'professional-draw', timelineFile: 'timeline.json'};
const out = resolve(process.argv[2] ?? 'out/professional-draw');
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
		assert.deepEqual([comp.width, comp.height, comp.fps, comp.durationInFrames], [1920, 1080, 30, 3540]);
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
		}), comp, serialize(comp.props));		const seek = (frame) => seekToFrame({frame, page, composition: 'C', timeoutInMilliseconds, logLevel: 'error',
			indent: false, attempt: 1});
		const sample = async (frame) => {
			await seek(frame);
			return page.evaluate(({pen}) => {
				const path = document.querySelector('[data-el^="ink-"] path[stroke-dashoffset]');
				const hand = document.querySelector('img[data-draw-hand]');
				const regionPaths = Array.from(document.querySelectorAll('[data-illustration-regions] mask path'));
				const active = document.querySelectorAll('[data-el^="ink-"] path[stroke-dashoffset]').length;
				const phase = hand?.dataset.drawHand ?? '';
				const scene = Array.from(document.querySelectorAll('[data-scene]'), (el) => {
					const b = el.getBoundingClientRect();
					return [el.dataset.scene,b.left,b.right,getComputedStyle(el).overflow];
				});
				let tip = null;
				let target = null;
				if (hand) {
					// Travel rotation/scale pivot is the tip itself, so this position stays fixed through the transform.
					const bounds = hand.getBoundingClientRect();
					tip = phase === 'stroke'
						? [bounds.left + bounds.width / hand.naturalWidth * pen.x,
							bounds.top + bounds.height / hand.naturalHeight * pen.y]
						: [parseFloat(hand.style.left) + parseFloat(hand.style.width) / hand.naturalWidth * pen.x,
							parseFloat(hand.style.top) + parseFloat(hand.style.height) / hand.naturalHeight * pen.y];
				}
				if (path) {
					const local = path.getPointAtLength(path.getTotalLength() - Number(path.getAttribute('stroke-dashoffset')));
					const p = local.matrixTransform(path.getScreenCTM());
					target = [p.x,p.y];
				}
				return {phase, tip, target, active, scene,
					handCount: document.querySelectorAll('[data-draw-hand],[data-carry-hand]').length,
					colors: regionPaths.map((region) => Number(region.getAttribute('opacity'))),
					finalImage: Boolean(document.querySelector('[data-illustration-final]'))};
			}, tips);
		};
		const groups = {};
		const csv = ['frame,time_s,scene,phase,tip_x,tip_y,stroke_x,stroke_y,error_px,finished_color_regions'];
		const repeats = new Map();
		let previous = null;
		let transitionFrames = 0;
		for (let frame = 0; frame < comp.durationInFrames; frame++) {
			const t = frame / comp.fps;
			const index = timeline.scenes.findIndex((s) => t >= s.start && t < s.end);
			const scene = timeline.scenes[index];
			const sliding = index + 1 < timeline.scenes.length && t >= timeline.scenes[index + 1].start - .72;
			if (!sliding && !scene.penTravel && frame % 15 !== 0) continue;
			const row = await sample(frame);
			if (frame % 75 === 0) repeats.set(frame, row);
			assert(row.handCount <= 1, `multiple hands at ${frame}`);
			if (sliding) {
				assert.equal(row.handCount, 0);
				assert.equal(row.scene.length, 2);
				near(row.scene[0][2], row.scene[1][1]);
				assert(row.scene.every((r) => r[3] === 'hidden'));
				transitionFrames++;
				previous = null;
				continue;
			}
			if (!scene.penTravel) continue;
			const result = groups[scene.id] ??= {inkFrames: 0, penUpFrames: 0, maxPx: 0, rmsPx: 0,
				maxConsecutiveStepPx: 0, regionalFrames: 0, inkAndColorFrames: 0};
			assert(row.active <= 1);
			if (row.phase === 'travel') {
				assert.equal(row.active, 0, `ink during pen-up at ${frame}`);
				result.penUpFrames++;
			}
			const activeStroke = scene.elements.some((e) => e.hand && t >= e.enterAt &&
				t < e.enterAt + e.enterDuration - 1e-8);
			if (activeStroke) assert.equal(row.phase, 'stroke', `missing stroke at ${frame}`);
			if (previous?.frame === frame-1 && row.tip && previous.tip) {
				const travel = Math.hypot(row.tip[0]-previous.tip[0],row.tip[1]-previous.tip[1]);
				result.maxConsecutiveStepPx = Math.max(result.maxConsecutiveStepPx,travel);
				assert(travel < 200, `pen displacement at frame ${frame}: ${travel}`);
			}
			previous = {frame,tip:row.tip};
			let error = '';
			if (row.target && row.tip) {
				error = Math.hypot(row.target[0]-row.tip[0],row.target[1]-row.tip[1]);
				assert(error < .1,`pen contact at frame ${frame}: ${error}`);
				result.inkFrames++;
				result.maxPx = Math.max(result.maxPx,error);
				result.rmsPx += error*error;
			}
			if (row.colors.some((p)=>p>0) && row.colors.some((p)=>p<1)) {
				result.regionalFrames++;
				if (row.active) result.inkAndColorFrames++;
			}
			if (row.tip) csv.push([frame,t,scene.id,row.phase,...row.tip,...(row.target ?? ['','']),error,
				row.colors.filter((p)=>p>=1).length].join(','));
		}
		for (const [id,result] of Object.entries(groups)) {
			assert(result.inkFrames > 60 && result.penUpFrames > 15,id);
			if (['robot-full','rover-full','close-up'].includes(id)) {
				assert(result.inkAndColorFrames > 30 && result.regionalFrames > 70,id);
			}
			result.rmsPx = Math.sqrt(result.rmsPx/result.inkFrames);
		}
		for (const frame of [...repeats.keys()].reverse().filter((_,i)=>i%5===0))
			assert.deepEqual(await sample(frame),repeats.get(frame), `frame order changed ${frame}`);
		const compare = timeline.scenes.find((scene) => scene.id === 'pixel-check');
		await seek((compare.start + 2)*30);
		const pixelRects = await page.evaluate(() => Object.fromEntries(['robot','rover','svg'].map(name => [
			name, ['finished','original'].map(kind => {
				const image = document.querySelector(`[data-el="${kind}-${name}"] img`);
				const box = image.getBoundingClientRect();
				return [box.left,box.top,box.right,box.bottom].map(Math.floor);
			}),
		])));
		const {value: {data: png}} = await page._client().send('Page.captureScreenshot',{format:'png'});
		assert(typeof png === 'string' && png.length > 100, 'missing comparison screenshot');
		await writeFile(join(out,'original-comparison.png'),Buffer.from(png,'base64'));
		await writeFile(join(out,'coordinates.csv'),csv.join('\n')+'\n');
		await writeFile(join(out,'browser-verification.json'),JSON.stringify({
			frames: comp.durationInFrames, groups,transitionFrames,pixelRects,
			pen: tips.pen,penTolerancePx:.1,deterministicSamples:Math.ceil(repeats.size/5),
		},null,2)+'\n');
		console.log(JSON.stringify(groups));

	} finally {
		await browser?.close({silent: true});
		await server?.closeServer();
		await rm(tmp, {recursive: true, force: true});
	}
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
