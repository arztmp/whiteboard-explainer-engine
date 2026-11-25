const {readFileSync} = require('node:fs');
const {openBrowser} = require('@remotion/renderer');

async function main() {
	const job = JSON.parse(readFileSync(0, 'utf8'));
	job.png = readFileSync(job.source).toString('base64');
	const browser = await openBrowser('chrome', {browserExecutable:process.argv[2], logLevel:'error'});
	try {
		const page = await browser.newPage({context:()=>null,logLevel:'error',indent:false,pageIndex:0,onBrowserLog:null,onLog:()=>{}});
		const result = await page.evaluate(async ({png, area, paths}) => {
			const {x,y,width,height} = area;
			const layer = () => Object.assign(document.createElement('canvas'), {width,height})
				.getContext('2d', {willReadFrequently:true});
			const raster = layer(), mask = layer(), ink = layer(), composite = layer(), cleanInk = layer();
			const source = new Image();
			source.src = 'data:image/png;base64,' + png;
			await source.decode();
			raster.drawImage(source,0,0,width,height);
			const original = raster.getImageData(0,0,width,height).data;
			const states = paths.map((p,index) => ({...p,index,geometry:new Path2D(p.d)}));
			const clear = ctx => {
				ctx.globalCompositeOperation='source-over';
				ctx.clearRect(0,0,width,height);
			};
			const paint = p => {
				const ctx = p.phase==='color' ? mask : ink;
				ctx.save();
				ctx.translate(-x,-y);
				ctx.lineCap=ctx.lineJoin='round';
				ctx.strokeStyle=p.phase==='color' ? '#fff' : p.stroke;
				ctx.lineWidth=p.width;
				ctx.stroke(p.geometry);
				ctx.restore();
			};
			const capture = () => {
				clear(composite);
				composite.drawImage(raster.canvas,0,0);
				composite.globalCompositeOperation='destination-in';
				composite.drawImage(mask.canvas,0,0);
				clear(cleanInk);
				cleanInk.drawImage(ink.canvas,0,0);
				cleanInk.globalCompositeOperation='destination-out';
				cleanInk.drawImage(mask.canvas,0,0);
				composite.globalCompositeOperation='source-over';
				composite.drawImage(cleanInk.canvas,0,0);
				return composite.getImageData(0,0,width,height).data;
			};
			const rebuild = list => {
				clear(ink);
				clear(mask);
				list.forEach(paint);
				return capture();
			};
			const diff = (left,right) => {
				let changed=0, visible=0, sourcePixels=0;
				const affected=[];
				for(let p=0;p<left.length;p+=4){
					const d=Math.max(Math.abs(left[p]-right[p]),Math.abs(left[p+1]-right[p+1]),
						Math.abs(left[p+2]-right[p+2]),Math.abs(left[p+3]-right[p+3]));
					if(d) {
						changed++;
						if(affected.length<256) affected.push([x+(p/4)%width+.5,y+Math.floor(p/4/width)+.5]);
						if(original[p+3]) sourcePixels++;
						// Contrast on the white board, including faint premultiplied edges.
						const a=left[p+3]/255,b=right[p+3]/255;
						if(Math.max(...[0,1,2].map(i=>Math.abs((255-left[p+i])*a-(255-right[p+i])*b)))>8) visible++;
					}
				}
				return {changed,visible,sourcePixels,affected:changed<=256 ? affected : []};
			};
			const analyze = list => {
				clear(ink);
				clear(mask);
				let previous=capture();
				return list.map(stroke=>{
					paint(stroke);
					const current=capture();
					const contribution=diff(previous,current);
					previous=current;
					return contribution;
				});
			};
			const baseline = analyze(states);
			const final = capture();
			let kept=states.filter((_,i)=>baseline[i].changed);
			const removed=states.filter((_,i)=>!baseline[i].changed).map(p=>({index:p.index,reason:'no-change'}));
			const pointToLine = ([x,y], points) => {
				let distance=Infinity;
				for(let i=1;i<points.length;i++){
					const [a,b]=points[i-1],dx=points[i][0]-a,dy=points[i][1]-b;
					const t=Math.min(1,Math.max(0,((x-a)*dx+(y-b)*dy)/(dx*dx+dy*dy || 1)));
					distance=Math.min(distance,Math.hypot(x-a-t*dx,y-b-t*dy));
				}
				return distance;
			};
			for(const candidate of states.filter((p,i)=>p.phase==='color' && baseline[i].visible<24 && baseline[i].changed)){
				if(!kept.includes(candidate)) continue;
				const trial=kept.filter(p=>p!==candidate);
				if(!diff(final,rebuild(trial)).changed){
					kept=trial;
					removed.push({index:candidate.index,reason:'covered-by-other-strokes'});
					continue;
				}
				// Query distance to the full neighboring route, including its long segments.

				const nearest=trial.filter(p=>p.phase==='color' && p.length>35 && baseline[p.index].visible>=24)
					.map(p=>({p,d:Math.min(...candidate.points.map(q=>pointToLine(q,p.points)))-p.width/2}))
					.sort((a,b)=>a.d-b.d).slice(0,7);
				for(const {p,d} of nearest){
					if(d>28) break;
					const previous=p.width;
					p.width+=Math.min(56,Math.max(12,2*d+24));
					if(!diff(final,rebuild(trial)).changed){
						kept=trial;
						removed.push({index:candidate.index,reason:'absorbed-by-neighbor',neighbor:p.index});
						break;
					}
					p.width=previous;
					// Attach only short nearby residuals; leave the original path
					// vertices in place and reuse the existing round brush.
					if(candidate.length>34) continue;
					const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
					const links=p.points.flatMap((point,i)=>[false,true].map(reverse=>{
						const part=reverse ? candidate.points.slice().reverse() : candidate.points;
						const next=p.points[i+1];
						return {i,part,cost:distance(point,part[0])+(next ? distance(part.at(-1),next)-distance(point,next) : 0)};
					})).sort((a,b)=>a.cost-b.cost);
					const old={width:p.width,points:p.points,geometry:p.geometry,d:p.d,length:p.length};
					let merged=false;
					for(const {i,part,cost} of links.slice(0,5)){
						if(cost>85) break;
						p.points=[...old.points.slice(0,i+1),...part,...old.points.slice(i+1)];
						p.d='M'+p.points.map(([x,y])=>x.toFixed(3)+' '+y.toFixed(3)).join(' L');
						p.geometry=new Path2D(p.d);
						p.length=p.points.slice(1).reduce((sum,q,j)=>sum+distance(p.points[j],q),0);
						for(const width of [old.width,Math.max(old.width,candidate.width)+2]){
							p.width=width;
							if(!diff(final,rebuild(trial)).changed){merged=true;break;}
						}
						if(merged) break;
					}
					if(merged){
						kept=trial;
						removed.push({index:candidate.index,reason:'joined-to-neighbor',neighbor:p.index});
						break;
					}
					Object.assign(p,old);
				}
			}
			// A residual at an already painted border can contribute full pigment
			// when it runs earlier, before the neighboring brush covers that edge.
			let audit=analyze(kept);
			for(const residual of kept.filter((p,i)=>p.phase==='color' && audit[i].visible<24)){
				const i=kept.indexOf(residual);
				const earlier=kept.map((p,j)=>({p,j})).filter(({p,j})=>j<i && p.phase==='color'
					&& p.points.some(a=>residual.points.some(b=>Math.hypot(a[0]-b[0],a[1]-b[1])<(p.width+residual.width)/2)));
				for(const {j} of earlier){
					const trial=kept.filter(p=>p!==residual);
					trial.splice(j,0,residual);
					const probe=analyze(trial);
					if(probe.filter(p=>p.visible<24).length < audit.filter(p=>p.visible<24).length
						&& !diff(final,capture()).changed){
						kept=trial;
						audit=probe;
						break;
					}
				}
			}
			// Cover the actual remaining PNG samples, rather than the much
			// larger synthetic support associated with a residual route.
			for(const residual of kept.filter((p,i)=>p.phase==='color' && audit[i].visible<24 && audit[i].affected.length)){
				const i=kept.indexOf(residual);
				const targets=audit[i].affected;
				const trial=kept.filter(p=>p!==residual);
				const options=trial.filter(p=>p.phase==='color' && baseline[p.index].visible>=24)
					.map(p=>({p,required:2*(Math.max(...targets.map(q=>pointToLine(q,p.points)))+2)}))
					.sort((a,b)=>(a.required-a.p.width)-(b.required-b.p.width));
				for(const {p,required} of options){
					const previous=p.width;
					p.width=Math.max(previous,required);
					if(p.width<=Math.max(previous*1.85,previous+42) && !diff(final,rebuild(trial)).changed){
						kept=trial;
						audit=analyze(kept);
						removed.push({index:residual.index,reason:'absorbed-source-fringe',neighbor:p.index});
						break;
					}
					p.width=previous;
				}
			}
			let optimized=analyze(kept);
			for(let i=0;i<kept.length;){
				if(optimized[i].visible){i++;continue;}
				const candidate=kept[i];
				const trial=kept.filter(p=>p!==candidate);
				if(diff(final,rebuild(trial)).changed){i++;continue;}
				removed.push({index:candidate.index,reason:'redundant-after-cleanup'});
				kept=trial;
				optimized=analyze(kept);
				i=0;
			}
			// Restore the optimized accumulation after testing rejected removals.
			rebuild(kept);
			if(diff(final,capture()).changed) throw Error('Paint cleanup changed the final raster');
			return {baseline,optimized,removed,kept:kept.map(({index,width,d,points,length})=>({index,width,d,points,length}))};
		}, job);
		process.stdout.write(JSON.stringify(result));
	} finally { await browser.close({silent:true}); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
