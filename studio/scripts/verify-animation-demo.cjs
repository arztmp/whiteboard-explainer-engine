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
const inputProps = {videoId: 'full-animation-demo', timelineFile: 'timeline.json'};
const out = resolve(process.argv[2] ?? 'out/full-animation');
const browserExecutable = process.env.CHROME_PATH;
const timeoutInMilliseconds = 30000;
const serialize = (data) =>
	NoReactInternals.serializeJSONWithSpecialTypes({data, staticBase: null}).serializedString;
const near = (actual, expected, limit = .06) => assert(Math.abs(actual - expected) < limit, `${actual} vs. ${expected}`);

function readFrame(page, tips, grip, sampleIds) {
	return page.evaluate(({pen, finger}, gripPoint, ids) => {
		const element = (id) => document.querySelector(`[data-el="${id}"]`);
		const mark = (el, x, y) => {
			const span = document.createElement('span');
			Object.assign(span.style, {
				position: 'absolute', left: x + 'px', top: y + 'px', width: '0px', height: '0px',
			});
			el.append(span);
			const {x: clientX, y: clientY} = span.getBoundingClientRect();
			span.remove();
			return [clientX, clientY];
		};
		const spritePoint = (img, point) => {
			const b = img.getBoundingClientRect();
			return [b.left + b.width * point.x / img.naturalWidth, b.top + b.height * point.y / img.naturalHeight];
		};
		const penImage = document.querySelector('img[data-draw-hand]');
		const fingerNode = document.querySelector('[data-carry-hand]');
		const fingerImage = fingerNode?.querySelector('img');
		const hand = penImage ?? fingerImage;
		const phase = penImage?.dataset.drawHand ?? fingerNode?.dataset.carryHand ?? '';
		const bounds = hand?.getBoundingClientRect();
		const inView = Boolean(bounds && bounds.right > 0 && bounds.left < 1920 && bounds.bottom > 0 && bounds.top < 1080);
		const path = document.querySelector('[data-el^="ink-"] path[stroke-dashoffset]');
		const reveal = document.querySelector('[data-reveal-front]');
		const drag = element('drag-robot');
		let target = null;
		if (phase === 'stroke' && path) {
			const p = path.getPointAtLength(path.getTotalLength() - Number(path.getAttribute('stroke-dashoffset')));
			const point = p.matrixTransform(path.getScreenCTM());
			target = [point.x, point.y];
		}
		if (phase === 'stroke' && reveal) {
			const [x, y] = reveal.dataset.revealFront.split(',').map(Number);
			const b = reveal.getBoundingClientRect();
			target = [b.left + x * b.width, b.top + y * b.height];
		}
		if (drag && ['grip', 'carry', 'release'].includes(phase)) target = mark(drag, gripPoint.x, gripPoint.y);
		const tip = hand ? spritePoint(hand, penImage ? pen : finger) : null;
		const outline = document.querySelector('[data-morph]');
		const scatter = document.querySelector('[data-scatter]');
		const elements = ids.flatMap((id) => {
			const el = element(id);
			if (!el) return [];
			const css = getComputedStyle(el);
			const transform = new DOMMatrix(css.transform === 'none' ? undefined : css.transform);
			return [[id, {center: mark(el, 0, 0), opacity: Number(css.opacity), scale: Math.hypot(transform.a, transform.b),
				angle: Math.atan2(transform.b, transform.a) * 180 / Math.PI,
				origin: mark(el, -80, -60)}]];
		});
		const caption = element('sync-words');
		return {
			phase, tip, target, inView, hands: document.querySelectorAll('[data-draw-hand],[data-carry-hand]').length,
			sprite: hand?.src.split('/').at(-1) ?? '',
			scene: Array.from(document.querySelectorAll('[data-scene]'), (el) => {
				const b = el.getBoundingClientRect();
				const rule = el.querySelector('[data-el$="-rule"]').getBoundingClientRect();
				const title = el.querySelector('[data-el$="-title"]').getBoundingClientRect();
				return {id: el.dataset.scene, left: b.left, right: b.right, clipped: getComputedStyle(el).overflow === 'hidden',
					gap: rule.x - title.x};
			}),
			dragCenter: drag ? mark(drag, 0, 0) : null,
			drawCount: document.querySelectorAll('[data-el^="ink-"] path').length,
			morph: outline ? [Number(outline.dataset.morph), outline.getAttribute('points')] : null,
			scatter: scatter ? [Number(scatter.dataset.scatter), ...Array.from(scatter.querySelectorAll('svg'),
				(el) => [el.getAttribute('x'), el.getAttribute('y'), el.getAttribute('transform')])] : null,
			caption: caption ? [...caption.querySelectorAll('span')].find((el) => !!el.style.transform)?.textContent ?? '' : '',
			elements: Object.fromEntries(elements),
		};
	}, tips, grip, sampleIds);
}

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
		assert.deepEqual([comp.width, comp.height, comp.fps, comp.durationInFrames], [1920, 1080, 30, 4500]);
		const timeline = comp.props.timeline;
		const tips = {pen: timeline.hand.tip, finger: timeline.carryHand.tip};
		const drag = timeline.scenes.find((s) => s.id === 'drag').elements.find((e) => e.carry);
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
		const ids = timeline.scenes.flatMap((scene) => scene.elements.filter((e) =>
			e.id.startsWith('enter-') || e.id.startsWith('fade-') || e.id.startsWith('move-') || e.zoom).map((e) => e.id));
		const seek = (frame) => seekToFrame({frame, page, composition: 'C', timeoutInMilliseconds, logLevel: 'error',
			indent: false, attempt: 1});
		const sample = async (frame) => {
			await seek(frame);
			return readFrame(page, tips, drag.carry.grip, ids);
		};
		const samples = new Map();
		const records = [];
		const transitions = [];
		const contacts = {};
		let lastDrag = drag.x;
		for (let frame = 0; frame < comp.durationInFrames; frame++) {
			const t = frame / 30;
			const scene = timeline.scenes[Math.floor(frame / 300)];
			const boundary = frame % 300 >= 276 && frame < 4200;
			const contactScene = scene.penTravel || scene.id === 'drag';
			if (!contactScene && !boundary && frame % 15 !== 0) continue;
			const row = await sample(frame);
			assert(row.hands <= 1, `overlapping hands at ${frame}`);
			if (row.sprite) assert.equal(row.sprite, scene.id === 'drag' ? 'El.png' : 'Kalem_El.png');
			if (boundary) {
				assert.equal(row.hands, 0);
				assert.equal(row.scene.length, 2);
				near(row.scene[0].right, row.scene[1].left);
				assert(row.scene.every((s) => s.clipped));
				assert(row.scene[0].left <= .06 && row.scene[1].right >= 1919.94);
				near(row.scene[0].gap, row.scene[1].gap);
				transitions.push({frame, x: row.scene[1].left});
			}
			if (scene.penTravel && !boundary) {
				const steps = scene.elements.filter((e) => e.hand);
				const active = steps.find((e) => t >= e.enterAt && t < e.enterAt + e.enterDuration - 1e-9);
				if (active) assert.equal(row.phase, 'stroke', `missing pen at ${frame}`);
				const started = steps.filter((e) => e.type === 'path' && t >= e.enterAt).length;
				assert.equal(row.drawCount, started, `wrong number of visible paths at ${frame}`);
				if (t >= scene.penTravel.end) assert(!row.inView, `pen stayed at ${frame}`);
			}
			if (scene.id === 'drag' && !boundary) {
				assert(row.dragCenter && row.dragCenter[0] >= lastDrag, `drag moved backward at frame ${frame}`);
				near(row.dragCenter[1], drag.y);
				if (t < drag.carry.pickup) near(row.dragCenter[0], drag.x);
				if (t >= drag.carry.land) near(row.dragCenter[0], drag.carry.target.x);
				lastDrag = row.dragCenter[0];
			}
			if (row.target && row.tip) {
				const dx = row.tip[0] - row.target[0];
				const dy = row.tip[1] - row.target[1];
				const error = Math.hypot(dx, dy);
				assert(error < .1, `contact at frame ${frame} was off by ${error}`);
				const result = contacts[scene.id] ??= {count: 0, max: 0, squares: 0};
				result.max = Math.max(result.max, error);
				result.count++;
				result.squares += error * error;
				records.push([frame, t, scene.id, row.phase, ...row.tip, ...row.target, dx, dy, error].join(','));
			}
			if (frame % 15 === 0) samples.set(frame, row);
		}
		for (const id of ['writing', 'geometry', 'robot-trace', 'rover-trace', 'robot-reveal', 'rover-reveal', 'drag'])
			assert((contacts[id]?.count ?? 0) >= 80, `missing contact samples for ${id}`);
		assert.equal(transitions.length, 14 * 24);
		for (const check of [43.5, 53.5]) assert(samples.get(check * 30).target);
		const entranceScene = timeline.scenes.find((s) => s.id === 'entrances');
		for (const el of entranceScene.elements.filter((el) => el.type === 'image')) {
			const almost = await sample(Math.ceil((el.enterAt + .25) * 30));
			const settled = await sample(Math.ceil((el.enterAt + el.enterDuration + .1) * 30));
			const a = almost.elements[el.id];
			const b = settled.elements[el.id];
			near(b.center[0], el.x);
			near(b.center[1], el.y);
			near(b.angle, 0);
			near(b.scale, 1);
			near(b.opacity, 1);
			if (el.enter === 'slide') assert(Math.hypot(a.center[0] - b.center[0], a.center[1] - b.center[1]) > 10);
			if (el.enter === 'rotate') assert(Math.abs(a.angle) > 45);
			if (el.enter === 'grow') assert(a.scale < .84);
			if (el.enter === 'fade') assert(a.opacity < .4);
		}
		assert(samples.get(72 * 30).elements['fade-robot'].opacity < 1);
		assert(samples.get(77 * 30).elements['fade-robot'].opacity < 1);
		assert(!samples.get(79 * 30).elements['fade-robot']);
		const morph = [81, 84.5, 88].map((t) => samples.get(t * 30).morph);
		assert(morph[0][0] === 0 && morph[2][0] === 1 && morph[1][0] > 0 && morph[1][0] < 1);
		assert(new Set(morph.map((m) => m[1])).size === 3);
		assert(morph.every((m) => m[1].split(' ').length === 192));
		const zoom = [90.5, 93.5, 98].map((t) => samples.get(t * 30).elements['zoom-rover']);
		near(zoom[0].scale, 1);
		near(zoom[1].scale, 1.48);
		near(zoom[2].scale, 1);
		zoom[1].origin.forEach((n, i) => near(n, zoom[0].origin[i]));
		const scatter = [100.5, 102.5, 104, 106.5, 108].map((t) => samples.get(t * 30).scatter);
		assert(!scatter[0] && !scatter[4] && scatter.slice(1, 4).every((value) => value.length === 141));
		assert(scatter[2][0] > scatter[1][0] && scatter[2][0] > scatter[3][0]);
		const screenshot = async (frame) => {
			await seek(frame);
			return (await page._client().send('Page.captureScreenshot', {format: 'png'})).data;
		};
		assert.equal(await screenshot(100.5 * 30), await screenshot(108 * 30), 'scatter did not restore original pixels');
		const movement = [120.5, 124, 127, 129].map((t) => samples.get(t * 30).elements);
		assert(movement[1]['move-rover'].center[0] > movement[0]['move-rover'].center[0]);
		assert(movement[2]['move-rover'].opacity < 1 && movement[2]['move-rover'].scale < 1);
		assert(movement[3]['move-robot'].center[0] < 0);
		near(movement[3]['move-rover'].center[0], 1455);
		await seek(124 * 30);
		assert(await page.evaluate(() => {
			const order = [...document.querySelectorAll('[data-el]')].map((el) => el.dataset.el);
			return order.indexOf('move-rover') < order.indexOf('move-robot');
		}));
		const words = timeline.scenes.at(-1).elements.find((e) => e.type === 'caption').words;
		for (const word of words) {
			const start = Math.ceil(word.start * 30 - 1e-8);
			assert.equal((await sample(start - 1)).caption, '');
			assert.equal((await sample(start)).caption, word.text);
			assert.equal((await sample(Math.ceil(word.end * 30 + .001))).caption, '');
		}
		for (const frame of [3195, 2550, 1875, 1305, 1065, 765, 435, 75, 3450, 3960, 4380])
			assert.deepEqual(await sample(frame), samples.get(frame), `non-deterministic seek at frame ${frame}`);
		const summary = Object.fromEntries(Object.entries(contacts).map(([id, s]) =>
			[id, {frames: s.count, maxPx: s.max, rmsPx: Math.sqrt(s.squares / s.count)}]));
		await writeFile(join(out, 'coordinates.csv'),
			['frame,time_s,scene,phase,tip_x,tip_y,target_x,target_y,dx,dy,error_px', ...records].join('\n') + '\n');
		await writeFile(join(out, 'browser-checks.json'), JSON.stringify({
			contacts: summary, tolerancePx: .1, transitionFrames: transitions.length, visualWordCues: words,
			deterministicSeeks: 11, scatterPixelRestore: true, sceneCount: 15,
		}, null, 2) + '\n');
		console.log(JSON.stringify(summary));
	} finally {
		await browser?.close({silent: true});
		await server?.closeServer();
		await rm(tmp, {recursive: true, force: true});
	}
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
