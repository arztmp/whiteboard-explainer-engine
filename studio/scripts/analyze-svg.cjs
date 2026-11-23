#!/usr/bin/env node
const {readFileSync} = require('node:fs');
const {openBrowser} = require('@remotion/renderer');

async function main() {
	const xml = readFileSync(0, 'utf8');
	const browser = await openBrowser('chrome', {browserExecutable: process.argv[2], logLevel: 'error'});
	try {
		const page = await browser.newPage({context: () => null, logLevel: 'error', indent: false,
			pageIndex: 0, onBrowserLog: null, onLog: () => {}});
		const result = await page.evaluate((xml) => {
			const svg = document.body.appendChild(document.importNode(new DOMParser().parseFromString(xml,'image/svg+xml').documentElement,true));
			const v = svg.viewBox.baseVal;
			const width = v.width || svg.width.baseVal.value, height = v.height || svg.height.baseVal.value;
			if (!(width > 0 && height > 0)) throw Error('SVG needs dimensions');
			const transform = svg.getScreenCTM().inverse();
			const paths = [];
			for (const node of svg.querySelectorAll('path,line,polyline,polygon,circle,ellipse,rect')) {
			  if (node.closest('defs,clipPath,mask,pattern,marker,symbol')) continue;
			  const css = getComputedStyle(node);
			  if(css.visibility==='hidden' || css.display==='none' || !node.getScreenCTM()) continue;
			  let length;
			  try { length=node.getTotalLength(); } catch { continue; }
			  const matrix = transform.multiply(node.getScreenCTM());
			  const count = Math.max(2,Math.min(1200,Math.ceil(length*Math.max(Math.hypot(matrix.a,matrix.b),Math.hypot(matrix.c,matrix.d))*540/Math.max(width,height)/1.7)));
			  let part = [];
			  for(let i=0;i<=count;i++) {
			    const position = node.getPointAtLength(i*length/count);
			    if (position === null) continue;
			    const at = [position.x,position.y];
			    if(part.length && Math.hypot(at[0]-part.at(-1).raw[0],at[1]-part.at(-1).raw[1]) > length/count*2+.1) {
			      if(part.length>1) paths.push(part.map(point=>point.xy));
			      part=[];
			    }
			    const p=position.matrixTransform(matrix);
			    part.push({raw:at,xy:[(p.x-v.x)/width,(p.y-v.y)/height]});
			  }
			  if(part.length>1) paths.push(part.map(point=>point.xy));
			}
			return new Promise((resolve, reject) => {
			const image=new Image();
			image.onerror=reject;
			image.onload=()=>{
			  const canvas=document.createElement('canvas');
			  canvas.width=Math.max(1,Math.round(width/Math.max(width,height)*540));
			  canvas.height=Math.max(1,Math.round(height/Math.max(width,height)*540));
			  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
			  resolve({paths, width, height, png:canvas.toDataURL()});
			};
			image.src='data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
			});
		}, xml);
		process.stdout.write(JSON.stringify(result));
	} finally {
		await browser.close({silent: true});
	}
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
