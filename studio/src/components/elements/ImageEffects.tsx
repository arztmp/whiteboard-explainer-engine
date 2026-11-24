import React, {useId} from 'react';
import {Img} from 'remotion';
import {resolveAsset} from '../../lib/assets';
import {morphAt, revealAt, scatterAt, tileOffset} from '../../lib/image-effects';
import {easeInOut, progress} from '../../lib/math';
import type {ImageElement, MorphElement} from '../../types';
import type {ElProps} from './index';

export const SpecialImageView: React.FC<ElProps<ImageElement>> = ({r, s, ctx, t}) => {
	const {el, geom: {imageSize, box}} = r;
	const {w, h} = imageSize!;
	const src = resolveAsset(ctx.videoId, el.src);
	const id = useId().replace(/[^\w-]/g, '');
	const scatter = el.scatter && scatterAt(el.scatter, t);
	const p = s.draw ?? 1;
	if (scatter) {
		const {columns = 12, rows = 8} = el.scatter!;
		const tileW = w / columns;
		const tileH = h / rows;
		return (
			<svg data-scatter={scatter.amount} width={w} height={h}
				style={{position: 'absolute', left: box.ox, top: box.oy, overflow: 'visible'}}>
				<defs><image id={id} href={src} width={w} height={h} /></defs>
				{Array.from({length: columns * rows}, (_, i) => {
					const x = (i % columns) * tileW;
					const y = Math.floor(i / columns) * tileH;
					const {x: dx, y: dy, angle} = tileOffset(el.id, i, scatter.amount, scatter.direction, el.scatter!.rotation);
					return (
						<svg key={i} opacity={1 - (el.scatter!.fade ?? 0) * scatter.amount} x={x + dx} y={y + dy} width={tileW} height={tileH}
							viewBox={`${x} ${y} ${tileW} ${tileH}`} transform={`rotate(${angle} ${x + dx + tileW / 2} ${y + dy + tileH / 2})`}>
							<use href={`#${id}`} />
						</svg>
					);
				})}
			</svg>
		);
	}
	const reveal = el.reveal && p < 1 ? revealAt(p, el.reveal.rows ?? 8) : null;
	return <Img src={src} data-reveal-front={reveal ? `${reveal.x},${reveal.y}` : undefined}
		style={{position: 'absolute', width: w, height: h, left: box.ox, top: box.oy,
			clipPath: reveal?.clip, transform: el.flipX ? 'scaleX(-1)' : undefined}} />;
};

export const MorphView: React.FC<ElProps<MorphElement>> = ({r, t}) => {
	const {from, to, at, duration, fill, toFill} = r.el;
	const p = easeInOut(progress(t, at, duration));
	return (
		<svg width={1} height={1} style={{position: 'absolute', overflow: 'visible'}}>
			<polygon data-morph={p} points={morphAt(from, to, p)} fill={fill ?? '#244559'} style={toFill ? {fill: `color-mix(in srgb, ${fill ?? '#244559'} ${(1 - p) * 100}%, ${toFill})`} : undefined} />
		</svg>
	);
};
