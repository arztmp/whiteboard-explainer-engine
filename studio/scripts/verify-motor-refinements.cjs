const assert = require('node:assert/strict');
const {readFile, writeFile} = require('node:fs/promises');
const {join} = require('node:path');

const close = (a,b) => assert(Math.abs(a-b)<.08, `${a} vs. ${b}`);

module.exports = async ({timeline, seek, at, page, out}) => {
	const fixture = JSON.parse(await readFile('public/motor-demo/refinements-report.json', 'utf8'));
	const csv = ['frame,test,actual_x,actual_y,expected_x,expected_y,error_px'];
	const backgrounds = [];
	assert(!timeline.allowMorph && !timeline.scenes.some(s => s.elements.some(e => e.type === 'morph')));
	assert.equal(fixture.formulas.length, 14);
	for (const scene of timeline.scenes.slice(0,2)) {
		const bg = scene.elements.find(e => e.role === 'background');
		const c = bg.carry;
		let previousX = Infinity;
		let maxErrorPx = 0;
		let count = 0;
		for (let frame = Math.ceil(c.pickup*30); frame < c.land*30; frame+=3) {
			await seek(frame);
			const r = await page.evaluate((id,[l,t,r,b]) => {
				const stage = document.querySelector(`[data-el="${id}"] img`).getBoundingClientRect();
				const hand = document.querySelector('[data-carry-hand]');
				const image = hand.querySelector('img');
				const box = image.getBoundingClientRect();
				const sx = box.width/image.naturalWidth;
				const sy = box.height/image.naturalHeight;
				return {phase:hand.dataset.carryHand, left:stage.left, x:box.left+(l+r)/2*sx,
					wrist:box.top+b*sy,height:(b-t)*sy, pen:Boolean(document.querySelector('[data-draw-hand]'))};
			}, bg.id, fixture.handAlpha);
			assert.equal(r.phase,'carry');
			assert(!r.pen && r.left < previousX);
			previousX = r.left;
			close(r.height,fixture.handHeight);
			const expected = [r.left+fixture.backgroundInset,timeline.height];
			const d = Math.hypot(r.x-expected[0],r.wrist-expected[1]);
			assert(d<.1);
			maxErrorPx=Math.max(d,maxErrorPx);
			count++;
			csv.push([frame,scene.id,r.x,r.wrist,...expected,d].join(','));
		}
		assert.equal(c.land,c.release);
		for (const t of [c.land,c.end+.1,scene.end-1.1]) {
			const r = await at(Math.round(t*30),{id:bg.id,local:c.grip});
			close(r.center[0],timeline.width/2);
			close(r.center[1],timeline.height/2);
			assert(r.backgroundBehind);
			assert(t===c.land ? r.phase==='exit' : !['exit','carry','grip'].includes(r.phase));
		}
		assert(scene.elements.every(el=>el.type!=='rect' && (el.type!=='text' || !el.box)));
		backgrounds.push({id:scene.id,count,maxErrorPx});
	}

	const formulas = [];
	for (const formula of fixture.formulas) {
		const scene = timeline.scenes.find(s=>s.start<=formula.start && s.end>formula.end);
		assert(!scene.elements.some(e=>e.type==='formula'));
		let maxErrorPx = 0;
		for (const id of formula.strokes) {
			const stroke=scene.elements.find(e=>e.id===id);
			assert(stroke?.enter==='draw' && stroke.hand);
			const frame=Math.round((stroke.enterAt+stroke.enterDuration/2)*30);
			const r=await at(frame);
			assert.equal(r.phase,'stroke',id);
			assert.equal(r.active,1,id);
			assert.equal(r.hands,1,id);
			const d=Math.hypot(r.tip[0]-r.target[0],r.tip[1]-r.target[1]);
			assert(d<.1,id);
			maxErrorPx=Math.max(d,maxErrorPx);
			csv.push([frame,id,...r.tip,...r.target,d].join(','));
		}
		await seek(Math.ceil((formula.end+.12)*30));
		const done=await page.evaluate(ids=>ids.every(id=>
			document.querySelector(`[data-el="${id}"] path:not([stroke-dashoffset])`)),formula.strokes);
		assert(done,formula.id);
		formulas.push({id:formula.id,label:formula.label,strokes:formula.strokes.length,maxErrorPx});
	}
	const zoom=timeline.scenes.find(s=>s.id==='zoom-refined');
	const bounds=async t=>{
		await seek(Math.round((zoom.start+t)*30));
		return page.evaluate(()=>['zoom-clock','zoom-webb','zoom-clock-caption','zoom-webb-caption'].map(id=>{
			const node=document.querySelector(`[data-el="${id}"]`);
			const b=(node.querySelector('img') ?? node.firstElementChild).getBoundingClientRect();
			return [b.left,b.top,b.right,b.bottom,b.width];
		}));
	};
	const initial=await bounds(.1);
	const compare=(actual,expected)=>actual.forEach((r,i)=>r.forEach((v,j)=>close(v,expected[i][j])));
	compare(await bounds(11),initial);
	let minimumObjectGapPx=Infinity;
	let minimumCaptionGapPx=Infinity;
	for(let t=1;t<=10.75;t+=.25){
		const [left,right,a,b]=await bounds(t);
		minimumObjectGapPx=Math.min(minimumObjectGapPx,right[0]-left[2]);
		minimumCaptionGapPx=Math.min(minimumCaptionGapPx,b[0]-a[2]);
		assert(Math.max(left[3],right[3]) < Math.min(a[1],b[1]));
		compare([a,b],initial.slice(2));
	}
	assert(minimumObjectGapPx>30 && minimumCaptionGapPx>30);
	assert((await bounds(2.6))[0][4]>initial[0][4]*1.3);
	assert((await bounds(7.4))[1][4]>initial[1][4]*1.2);
	const report={backgrounds,formulas,zoom:{minimumObjectGapPx,minimumCaptionGapPx,returnedToInitial:true}};
	await writeFile(join(out,'refinements-browser.json'),JSON.stringify(report,null,2)+'\n');
	await writeFile(join(out,'refinements-coordinates.csv'),csv.join('\n')+'\n');
	console.log(JSON.stringify(report));
};
