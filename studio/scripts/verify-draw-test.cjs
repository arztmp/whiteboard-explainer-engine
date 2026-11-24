const assert = require('node:assert/strict');
const {mkdir, writeFile} = require('node:fs/promises');
const {join} = require('node:path');

module.exports = async ({timeline, seek, page, out}) => {
	const output = join(out, 'pixel-evidence');
	await mkdir(output, {recursive: true});
	const capture = async (file) => {
		const {value:{data}} = await page._client().send('Page.captureScreenshot', {format:'png'});
		if (file) await writeFile(join(output, file+'.png'), Buffer.from(data, 'base64'));
		return data;
	};
	await page.evaluate(() => {
		const style = document.createElement('style');
		style.textContent = '[data-draw-hand] { visibility:hidden !important }';
		document.head.append(style);
	});
	const reports = [];
	const probes = [];
	const csv = ['scene,stroke,phase,frame,tip_x,tip_y,route_x,route_y,error_px'];
	for (const scene of timeline.scenes) {
		const paths = scene.elements.filter(e=>e.paintFor);
		let maximumErrorPx = 0;
		const inspect = (id, from) => page.evaluate(({id, tip, from}) => {
			const route = document.querySelector(`[data-color-route="${id}"],[data-ink-route="${id}"]`);
			const hand = document.querySelector('[data-draw-hand]');
			if (!route || hand?.dataset.drawHand !== 'stroke') return null;
			const scene = route.ownerSVGElement;
			const length = route.getTotalLength();
			const p = route.getPointAtLength(length).matrixTransform(scene.getScreenCTM());
			const rect = hand.getBoundingClientRect();
			const x = rect.left + tip.x * rect.width / hand.naturalWidth;
			const y = rect.top + tip.y * rect.height / hand.naturalHeight;
			const swept = from === undefined ? [] : Array.from({length:Math.max(2,Math.ceil(length-from)+1)}, (_,i) => {
				const q = route.getPointAtLength(Math.min(from+i,length)).matrixTransform(scene.getScreenCTM());
				return [q.x,q.y];
			});
			return {x,y,routeX:p.x, routeY:p.y,length,swept, radius:Number(route.getAttribute('stroke-width'))/2};
		}, {id, tip:timeline.hand.tip, from});
		for (const stroke of paths) {
			const frame = Math.round((stroke.enterAt+stroke.enterDuration*.5)*30);
			await seek(frame);
			const row = await inspect(stroke.id);
			assert(row, `${scene.id}/${stroke.id} missing contact`);
			const d = Math.hypot(row.x-row.routeX,row.y-row.routeY);
			assert(d<.1, `${scene.id}/${stroke.id} pen distance ${d}`);
			maximumErrorPx = Math.max(d,maximumErrorPx);
			csv.push([scene.id,stroke.id,stroke.paintFor.phase,frame,row.x,row.y,row.routeX,row.routeY,d].join(','));
		}
		const color = paths.filter(e=>e.paintFor.phase==='color');
		assert(color.length>3);
		const phases = [...new Set(paths.map(e=>e.paintFor.phase))];
		assert.deepEqual(phases, scene.id==='galaxy'||scene.id==='clock' ? ['color'] : ['outline','detail','color']);
		for (const fraction of [.12,.46,.77]) {
			const stroke = color.slice().sort((a,b)=>b.enterDuration-a.enterDuration)[Math.floor(fraction*6) % color.length];
			const frame = Math.round((stroke.enterAt+stroke.enterDuration*.48)*30);
			await seek(frame);
			const a = await inspect(stroke.id);
			const key=scene.id+'-'+fraction;
			await capture(key+'-before');
			await seek(frame+1);
			const b = await inspect(stroke.id,a?.length);
			assert(a&&b);
			await capture(key+'-after');
			probes.push({key,a,b});
		}
		let gapSamples=0;
		for (const i of [2,Math.floor(paths.length*.48),paths.length-2]) {
			const a = paths[i], b = paths[i+1];
			const frame = Math.ceil((a.enterAt+a.enterDuration)*30)+1;
			assert(frame+1 < b.enterAt*30);
			await seek(frame);
			const before = await capture();
			await seek(frame+1);
			assert.equal(await capture(),before, `${scene.id} paint changed in midair`);
			gapSamples++;
		}
		await seek(Math.round(scene.end*30)-20);
		await page.evaluate(() => {
			// Compare against the original on a colored background, so alpha errors show.
			document.querySelector('[data-scene]').style.background = '#83d1b9';
		});
		await capture(scene.id+'-painted');
		const alphaDifferentPixels = await page.evaluate(async () => {
			const canvas = document.querySelector('[data-painted-source]');
			const image = new Image();
			image.src = canvas.dataset.paintedSource;
			await image.decode();
			const ctx = canvas.getContext('2d');
			const actual = ctx.getImageData(0,0,canvas.width,canvas.height).data;
			ctx.clearRect(0,0,canvas.width,canvas.height);
			ctx.drawImage(image,0,0,canvas.width,canvas.height);
			const expected = ctx.getImageData(0,0,canvas.width,canvas.height).data;
			let different = 0;
			for (let i = 3; i < actual.length; i += 4) if (actual[i] !== expected[i]) different++;
			return different;
		});
		assert.equal(alphaDifferentPixels,0, `${scene.id} alpha differs from source`);
		await capture(scene.id+'-original');
		// Rebuild DOM for the next scene; browser QA always seeks the same timeline.
		reports.push({id:scene.id, phases, pathSamples:paths.length, gapSamples, maximumErrorPx, alphaDifferentPixels});
	}
	await writeFile(join(out,'contact.csv'),csv.join('\n')+'\n');
	await writeFile(join(out,'browser.json'),JSON.stringify({scenes:reports,probes},null,2)+'\n');
	console.log(JSON.stringify(reports));
};
