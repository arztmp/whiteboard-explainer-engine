import katex from 'katex';
import 'katex/dist/katex.min.css';
import theme from '../theme.json';
import {IllustrationView} from './elements/IllustrationView';
import {MorphView, SpecialImageView} from './elements/ImageEffects';
import React, {useMemo} from 'react';
import {Img} from 'remotion';
import {sampleSceneAnimation, type ElementState} from '../lib/anim';
import {resolveAsset} from '../lib/assets';
import {resolveElement, type Ctx, type Resolved} from '../lib/resolve';
import type {HandConfig, Scene, Timeline} from '../types';
import {
	BarView,
	CaptionView,
	CardView,
	ClockView,
	CounterView,
	ImageView,
	PathView,
	ShapeView,
	TextView,
} from './elements';

export const useResolvedScene = (scene: Scene, ctx: Ctx, fontsOk: boolean): Resolved[] =>
	// eslint-disable-next-line react-hooks/exhaustive-deps
	useMemo(() => scene.elements.map((el) => resolveElement(el, scene, ctx)), [scene, ctx, fontsOk]);

const formulaCache = new Map<string, string>();
const formulaMarkup = (latex: string) => {
	const existing = formulaCache.get(latex);
	if (existing !== undefined) return existing;
	const html = katex.renderToString(latex, {throwOnError: true, trust: false, output: 'htmlAndMathml', maxExpand: 1000});
	formulaCache.set(latex, html);
	return html;
};

const ElementBody: React.FC<{r: Resolved; s: ElementState; ctx: Ctx; t: number}> = ({r, s, ctx, t}) => {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const props = {r, s, ctx, t} as any;
	switch (r.el.type) {
		case 'formula': {
			const {el} = r;
			return <div data-formula={el.latex} style={{position: 'absolute', left: 0, top: 0,
				transform: 'translate(-50%, -50%)', whiteSpace: 'nowrap', fontSize: el.size ?? 52,
				color: el.color ?? theme.navy}}
				dangerouslySetInnerHTML={{__html: formulaMarkup(el.latex)}} />;
		}
		case 'image':
			if (r.el.illustration) return <IllustrationView {...props} />;
			return r.el.reveal || r.el.scatter ? <SpecialImageView {...props} /> : <ImageView {...props} />;
		case 'morph':
			return <MorphView {...props} />;
		case 'text':
			return <TextView {...props} />;
		case 'counter':
			return <CounterView {...props} />;
		case 'card':
			return <CardView {...props} />;
		case 'bar':
			return <BarView {...props} />;
		case 'path':
			return <PathView {...props} />;
		case 'rect':
		case 'circle':
			return <ShapeView {...props} />;
		case 'clock':
			return <ClockView {...props} />;
		case 'caption':
			return <CaptionView {...props} />;
		default:
			return null;
	}
};

/**
 * Nội dung 1 scene trong hệ toạ độ 1920x1080 của scene.
 * layer='elements' vẽ các element; layer='hands' chỉ vẽ tay (đặt trên cùng).
 */
export const SceneContent: React.FC<{
	resolved: Resolved[];
	ctx: Ctx;
	t: number;
	layer: 'elements' | 'hands';
	hand?: HandConfig | null;
	penTravel?: Scene['penTravel'];
	carryHand?: Timeline['carryHand'];
}> = ({resolved, ctx, t, layer, hand, carryHand, penTravel}) => {
	const {items, hand: selected} = sampleSceneAnimation(resolved, t, ctx.fps, penTravel);

	if (layer === 'hands') {
		if (selected.kind === 'carry' && carryHand) {
			const pose = selected.pose;
			const src = resolveAsset(ctx.videoId, carryHand.src);
			const nat = ctx.imageSizes[src] ?? {w: 400, h: 400};
			const scale = pose.scale ?? carryHand.scale ?? 1;
			const {columns, rows} = carryHand.grid ?? {columns: 1, rows: 1};
			const index = Math.round(pose.closed * (columns * rows - 1));
			const width = nat.w * scale / columns;
			const height = nat.h * scale / rows;
			return (
				<div
					data-carry-hand={pose.phase}
					style={{position: 'absolute', left: pose.x, top: pose.y, transform: `rotate(${pose.rotate}deg)`,
						transformOrigin: '0 0', pointerEvents: 'none'}}
				>
					<div data-carry-cell={index} style={{position: 'absolute', overflow: 'hidden', width, height,
						left: -carryHand.tip.x * scale, top: -carryHand.tip.y * scale}}>
						<Img src={src} style={{position: 'absolute', width: nat.w * scale, height: nat.h * scale,
							left: -(index % columns) * width, top: -Math.floor(index / columns) * height}} />
					</div>
				</div>
			);
		}
		if (!hand || selected.kind !== 'draw') return null;
		const url = resolveAsset(ctx.videoId, hand.src);
		const nat = ctx.imageSizes[url] ?? {w: 400, h: 400};
		const scale = (hand.scale ?? 1) * (penTravel?.scale ?? 1);
		const pose = selected.pose;
		if (!pose || pose.opacity <= 0.001) return null;
		return (
			<Img
				data-draw-hand={pose.active ? 'stroke' : 'travel'}
				src={url}
				style={{
					position: 'absolute',
					left: pose.x - hand.tip.x * scale,
					top: pose.y - hand.tip.y * scale,
					width: nat.w * scale,
					height: nat.h * scale,
					transform: pose.lift ? `rotate(${6 * pose.lift}deg) scale(${1 - .06 * pose.lift})` : undefined,
					transformOrigin: pose.lift ? `${hand.tip.x * scale}px ${hand.tip.y * scale}px` : undefined,
					opacity: pose.opacity,
					pointerEvents: 'none',
				}}
			/>
		);
	}

	return (
		<>
			{items.map(({r, state: s}) => {
				if (!s.visible) return null;
				const tf = [
					`translate(${s.dx.toFixed(2)}px, ${s.dy.toFixed(2)}px)`,
					s.rotate ? `rotate(${s.rotate}deg)` : '',
					s.scale !== 1 ? `scale(${s.scale.toFixed(4)})` : '',
					s.rotateY ? `perspective(1400px) rotateY(${s.rotateY.toFixed(2)}deg)` : '',
				].join(' ');
				return (
					<div
						key={r.el.id}
						data-el={r.el.id}
						style={{
							position: 'absolute',
							left: s.x,
							top: s.y,
							width: 0,
							height: 0,
							transform: tf,
							transformOrigin: '0 0',
							opacity: s.opacity,
							filter: r.el.inkShadow ? `drop-shadow(${r.el.inkShadow})` : undefined,
						}}
					>
						<ElementBody r={r} s={s} ctx={ctx} t={t} />
					</div>
				);
			})}
		</>
	);
};
