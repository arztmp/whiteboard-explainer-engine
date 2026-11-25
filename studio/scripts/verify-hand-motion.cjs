#!/usr/bin/env node
const assert = require('node:assert/strict');
const {mkdir, mkdtemp, rm, writeFile} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const {dirname, join, resolve} = require('node:path');
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition} = require('@remotion/renderer');
const {NoReactInternals} = require('remotion/no-react');

// Remotion's public rendering API doesn't expose the live composition DOM.
const renderer = dirname(require.resolve('@remotion/renderer'));
const {prepareServer} = require(join(renderer, 'prepare-server'));
const {setPropsAndEnv} = require(join(renderer, 'set-props-and-env'));
const {seekToFrame} = require(join(renderer, 'seek-to-frame'));

const inputProps = {videoId: 'hand-motion-demo', timelineFile: 'timeline.json'};
const output = resolve(process.argv[2] ?? 'out/hand-motion');
const browserExecutable = process.env.CHROME_PATH;
const timeoutInMilliseconds = 30000;
const serialize = (data) =>
	NoReactInternals.serializeJSONWithSpecialTypes({data, indent: undefined, staticBase: null}).serializedString;

const readFrame = (page, tips, grip) => page.evaluate(({pen, finger}, contact) => {
	const penImage = document.querySelector('img[data-draw-hand]');
	const fingerHand = document.querySelector('[data-carry-hand]');
	const fingerCell = fingerHand?.querySelector('[data-carry-cell]');
	const fingerImage = fingerCell?.querySelector('img');
	const paths = Array.from(document.querySelectorAll('[data-el^="ink-"] svg > path'));
	const fronts = paths.flatMap((path) => {
		const offset = path.getAttribute('stroke-dashoffset');
		return offset === null ? [] : [{path, offset: Number(offset)}];
	});
	const object = document.querySelector('[data-el="drag-object"]');

	const hit = (element, {x, y}) => {
		const mark = document.createElement('span');
		Object.assign(mark.style, {position: 'absolute', width: '0', height: '0', left: x + 'px', top: y + 'px'});
		element.append(mark);
		const rect = mark.getBoundingClientRect();
		mark.remove();
		return [rect.x, rect.y];
	};
	const imagePoint = (image, tip) => {
		const box = image.getBoundingClientRect();
		return [box.x + tip.x * box.width / image.naturalWidth, box.y + tip.y * box.height / image.naturalHeight];
	};
	const hand = penImage ?? fingerImage;
	const bounds = (penImage ?? fingerCell)?.getBoundingClientRect();
	const inView = !!bounds && bounds.right > 0 && bounds.bottom > 0 &&
		bounds.left < 1920 && bounds.top < 1080;
	const phase = penImage?.dataset.drawHand ?? fingerHand?.dataset.carryHand ?? '';
	const center = object ? hit(object, {x: 0, y: 0}) : null;
	let target = object ? hit(object, contact) : null;
	if (fronts.length === 1) {
		const {path, offset} = fronts[0];
		const local = path.getPointAtLength(path.getTotalLength() - offset);
		const screen = local.matrixTransform(path.getScreenCTM());
		target = [screen.x, screen.y];
	}
	const tip = hand ? imagePoint(hand, penImage ? pen : finger) : null;
	return {phase, inView, bothHands: !!penImage && !!fingerImage, inkCount: paths.length,
		activeInk: fronts.length, sprite: hand?.src.split('/').at(-1) ?? '', tip, target, center};
}, tips, grip);

async function run() {
	const tmp = await mkdtemp(join(tmpdir(), 'hand-motion-qa-'));
	let browser;
	let server;
	try {
		const serveUrl = await bundle({entryPoint: resolve('src/index.ts'), outDir: tmp, symlinkPublicDir: true});
		server = await prepareServer({webpackConfigOrServeUrl: serveUrl, port: null, remotionRoot: resolve('.'),
			sampleRate: 48000, logLevel: 'error', indent: false});
		browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
		const comp = await selectComposition({id: 'C', serveUrl: server.serveUrl, inputProps, puppeteerInstance: browser});
		assert.deepEqual([comp.width, comp.height, comp.fps, comp.durationInFrames], [1920, 1080, 30, 900]);
		const [write, draw, drag] = comp.props.timeline.scenes;
		const object = drag.elements.find((element) => element.id === 'drag-object');
		const strokeCounts = [write, draw].map((scene) => scene.elements.filter((element) => element.hand).length);
		const tips = {pen: comp.props.timeline.hand.tip, finger: comp.props.timeline.carryHand.tip};
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
		const sample = async (frame) => {
			await seekToFrame({frame, page, composition: comp.id, timeoutInMilliseconds, logLevel: 'error',
				indent: false, attempt: 1});
			return readFrame(page, tips, object.carry.grip);
		};
		const rows = [];
		const distances = {writing: [], drawing: [], dragging: []};
		const maxStep = {writing: 0, drawing: 0, dragging: 0};
		let lastTip = null;
		let lastX = object.x;
		for (let frame = 0; frame < comp.durationInFrames; frame++) {
			const row = await sample(frame);
			const t = frame / comp.fps;
			const scene = frame < 300 ? 'writing' : frame < 600 ? 'drawing' : 'dragging';
			const message = `frame ${frame} (${scene})`;
			const penScene = frame < 300 ? write : draw;
			if (frame % 300 === 0) lastTip = null;
			if (lastTip && row.tip) {
				const step = Math.hypot(row.tip[0] - lastTip[0], row.tip[1] - lastTip[1]);
				maxStep[scene] = Math.max(step, maxStep[scene]);
				assert(step < 225, `hand jumped at ${message}: ${step} px`);
			}
			lastTip = row.tip;
			assert(!row.bothHands, `two hands at ${message}`);
			if (row.sprite) assert.equal(row.sprite, frame < 600 ? 'Kalem_El.png' : 'El.png', message);
			if (frame < 600) {
				const strokes = penScene.elements.filter((element) => element.hand);
				const started = strokes.filter((element) => element.enterAt <= t).length;
				const active = strokes.filter((element) => element.enterAt <= t && t < element.enterAt + element.enterDuration).length;
				assert.equal(row.inkCount, started, `ink appeared early or disappeared at ${message}`);
				assert.equal(row.activeInk, active, `stroke progress at ${message}`);
				if (active) assert.equal(row.phase, 'stroke', message);
			} else {
				assert(row.center && row.center[0] >= lastX, `object moved backward at ${message}`);
				assert.equal(row.center[1], object.y, `vertical motion at ${message}`);
				if (t < object.carry.pickup) assert.equal(row.center[0], object.x, message);
				if (t >= object.carry.land) assert.equal(row.center[0], object.carry.target.x, message);
				lastX = row.center[0];
			}
			if ([0, 299, 300, 599, 600, 899].includes(frame)) assert(!row.inView, `hand on a scene cut at ${message}`);
			const locked = row.activeInk === 1 || (frame >= 600 && ['grip', 'carry', 'release'].includes(row.phase));
			let delta = [];
			if (locked) {
				assert(row.tip && row.target, `missing contact at ${message}`);
				const [dx, dy] = row.tip.map((value, axis) => value - row.target[axis]);
				const distance = Math.hypot(dx, dy);
				assert(distance < 0.1, `contact error at ${message}: ${distance}px`);
				distances[scene].push({dx, dy, distance, frame});
				delta = [dx, dy, distance];
			}
			rows.push({row, csv: [frame, t.toFixed(6), scene, row.phase, ...row.tip ?? ['', ''],
				...row.target ?? ['', ''], ...delta, ...Array(3 - delta.length).fill(''), row.inView].join(',')});
		}
		assert.equal(rows[299].row.inkCount, strokeCounts[0]);
		assert.equal(rows[599].row.inkCount, strokeCounts[1]);
		const repeat = [865, 705, 552, 341, 270, 157, 37, 0, 599, 800, 299, 680];
		for (const frame of repeat) assert.deepEqual(await sample(frame), rows[frame].row, `seek differs at frame ${frame}`);
		const summary = Object.fromEntries(Object.entries(distances).map(([scene, measured]) => {
			assert(measured.length > 90, `too few measured contact frames for ${scene}`);
			const peak = measured.reduce((max, point) => point.distance > max.distance ? point : max);
			return [scene, {frames: measured.length, peak,
				rms: Math.sqrt(measured.reduce((sum, p) => sum + p.distance ** 2, 0) / measured.length),
				maxHandStep: maxStep[scene]}];
		}));
		await mkdir(output, {recursive: true});
		const csv = ['frame,time_s,scene,phase,sprite_tip_x,sprite_tip_y,contact_x,contact_y,dx,dy,error_px,hand_in_view',
			...rows.map(({csv: line}) => line)];
		await writeFile(join(output, 'contact-coordinates.csv'), csv.join('\n') + '\n');
		await writeFile(join(output, 'contact-summary.json'), JSON.stringify({
			pngCalibration: tips, tolerancePx: 0.1, deterministicSamples: repeat, scenes: summary,
		}, null, 2) + '\n');
		console.log(summary);
	} finally {
		await browser?.close({silent: true});
		await server?.closeServer();
		await rm(tmp, {recursive: true, force: true});
	}
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
