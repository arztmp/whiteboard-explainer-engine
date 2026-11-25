import React, {useLayoutEffect, useRef, useState} from 'react';
import {cancelRender, continueRender, delayRender} from 'remotion';
import type {ElementState} from '../../lib/anim';
import {resolveAsset} from '../../lib/assets';
import type {ImageElement, PathElement} from '../../types';
import type {Ctx, Resolved} from '../../lib/resolve';

const lineCache = new WeakMap<PathElement, {x: number; y: number; at: number}[]>();

function prefix(path: Resolved<PathElement>, amount: number) {
	const full = path.geom.path!;
	let points = lineCache.get(path.el);
	if (!points) {
		let at = 0;
		points = Array.from(path.el.d.matchAll(/[ML](-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g),
			([, x, y]) => ({x: Number(x), y: Number(y), at: 0}));
		points.forEach((point, i) => {
			if (i) at += Math.hypot(point.x-points![i-1].x, point.y-points![i-1].y);
			point.at = at;
		});
		lineCache.set(path.el, points);
	}
	const length = full.length * amount;
	const tip = full.exactPointAt(length);
	return 'M' + points.filter((point, i) => i === 0 || point.at < length)
		.map(({x, y}) => `${x} ${y}`).join(' L') + ` L${tip.x} ${tip.y}`;
}

export const PenPaintView: React.FC<{
	r: Resolved<ImageElement>;
	ctx: Ctx;
	items: {r: Resolved; state: ElementState}[];
}> = ({r, ctx, items}) => {
	const {box, anchor} = r.geom;
	const area = {x: anchor.x + box.ox, y: anchor.y + box.oy, width: box.w, height: box.h};
	const strokes = items.flatMap(({r: path, state}) => {
		if (path.el.type !== 'path' || path.el.paintFor?.imageId !== r.el.id || !state.visible) return [];
		const p = state.draw ?? 1;
		if (p <= 0) return [];
		return [{
			id: path.el.id,
			phase: path.el.paintFor.phase,
			stroke: path.el.stroke ?? "#222B39",
			props: {
				d: p < 1 ? prefix(path as Resolved<PathElement>, p) : path.el.d, strokeWidth: path.el.strokeWidth, fill: 'none',
				strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
			},
		}];
	});
	const url = resolveAsset(ctx.videoId, r.el.src);
	const output = useRef<HTMLCanvasElement>(null);
	const buffers = useRef<{source: HTMLImageElement; mask: HTMLCanvasElement; ink: HTMLCanvasElement; raster: HTMLCanvasElement} | null>(null);
	const [source, setSource] = useState<HTMLImageElement | null>(null);
	const [handle] = useState(() => delayRender(`paint source ${url}`));
	useLayoutEffect(() => {
		let mounted = true;
		const image = new Image();
		image.src = url;
		image.decode().then(() => {
			if (mounted) setSource(image);
		}).catch(error => {
			if (mounted) cancelRender(error);
		});
		return () => { mounted = false; continueRender(handle); };
	}, [url, handle]);

	const pixelWidth = Math.round(box.w);
	const pixelHeight = Math.round(box.h);
	useLayoutEffect(() => {
		const canvas = output.current;
		if (!source || !canvas) return;
		if (!buffers.current || buffers.current.source !== source || buffers.current.mask.width !== canvas.width || buffers.current.mask.height !== canvas.height) {
			const layer = () => Object.assign(document.createElement('canvas'), {width:canvas.width, height:canvas.height});
			buffers.current = {source, mask:layer(), ink:layer(), raster:layer()};
			buffers.current.raster.getContext('2d')!.drawImage(source, 0, 0, canvas.width, canvas.height);
		}
		const {mask, ink, raster} = buffers.current;
		const colorCtx = mask.getContext('2d')!;
		const inkCtx = ink.getContext('2d')!;
		const visible = canvas.getContext('2d')!;
		const clear = (surface: CanvasRenderingContext2D) => {
			surface.resetTransform();
			surface.globalCompositeOperation = 'source-over';
			surface.clearRect(0,0,canvas.width,canvas.height);
		};
		clear(visible);
		clear(colorCtx);
		clear(inkCtx);
		for (const layer of [colorCtx, inkCtx]) {
			layer.scale(canvas.width/box.w,canvas.height/box.h);
			layer.translate(-area.x,-area.y);
			layer.lineCap = 'round';
			layer.lineJoin = 'round';
		}
		for (const stroke of strokes) {
			const layer = stroke.phase === 'color' ? colorCtx : inkCtx;
			layer.strokeStyle = stroke.phase === 'color' ? '#fff' : stroke.stroke;
			layer.lineWidth = stroke.props.strokeWidth!;
			layer.stroke(new Path2D(stroke.props.d));
		}
		visible.drawImage(raster,0,0);
		visible.globalCompositeOperation = 'destination-in';
		visible.drawImage(mask,0,0);
		inkCtx.resetTransform();
		inkCtx.globalCompositeOperation = 'destination-out';
		inkCtx.drawImage(mask,0,0);
		visible.globalCompositeOperation = 'source-over';
		visible.drawImage(ink,0,0);
		continueRender(handle);
	});

	const position = {position:'absolute' as const, left:box.ox, top:box.oy};
	return (
		<>
			<canvas ref={output} data-painted-source={url} width={pixelWidth} height={pixelHeight}
				style={{...position,width:box.w,height:box.h}} />
			<svg data-pen-paint={r.el.id} width={box.w} height={box.h}
				viewBox={`${area.x} ${area.y} ${area.width} ${area.height}`}
				style={{...position, visibility:'hidden'}} aria-hidden="true">
				{strokes.map(path => <path key={path.id} data-color-route={path.phase === 'color' ? path.id : undefined}
					data-ink-route={path.phase !== 'color' ? path.id : undefined} {...path.props} />)}
			</svg>
		</>
	);
};
