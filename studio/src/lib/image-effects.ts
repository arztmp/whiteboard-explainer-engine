import type {ImageElement, Vec} from '../types';
import {clamp, easeInOut, lerp, progress, seededRandom} from './math';

/** Both the pen and the image clip sample the same continuous scan front. */
export const revealAt = (p: number, rows: number) => {
	const row = Math.min(rows - 1, Math.floor(p * rows));
	const fraction = clamp(p * rows - row, 0, 1);
	const leftToRight = row % 2 === 0;
	const x = (leftToRight ? fraction : 1 - fraction) * 100;
	const top = 100 * row / rows;
	const bottom = 100 * (row + 1) / rows;
	const y = lerp(top, bottom, fraction);
	const clip = leftToRight
		? `polygon(0 0, 100% 0, 100% ${top}%, ${x}% ${top}%, ${x}% ${bottom}%, 0 ${bottom}%)`
		: `polygon(0 0, 100% 0, 100% ${bottom}%, ${x}% ${bottom}%, ${x}% ${top}%, 0 ${top}%)`;
	return {x: x / 100, y: y / 100, clip};
};

export const scatterAt = (effect: NonNullable<ImageElement['scatter']>, t: number) => {
	const {at, out, hold = 0, back} = effect;
	if (t <= at || t >= at + out + hold + back) return null;
	const returning = t >= at + out + hold;
	const p = returning ? 1 - easeInOut(progress(t, at + out + hold, back)) : easeInOut(progress(t, at, out));
	const blend = easeInOut(progress(t, at + out, hold));
	const from = effect.direction ?? {x: 0, y: -80};
	const to = effect.returnDirection ?? from;
	return {amount: p, direction: {x: lerp(from.x, to.x, blend), y: lerp(from.y, to.y, blend)}};
};

export const tileOffset = (id: string, index: number, amount: number, direction: Vec) => {
	const rand = seededRandom(`${id}:${index}`);
	const angle = rand() * 2 * Math.PI;
	const radius = 65 + rand() * 135;
	return {x: (direction.x + radius * Math.cos(angle)) * amount,
		y: (direction.y + radius * Math.sin(angle)) * amount, angle: (rand() - 0.5) * 62 * amount};
};

export const morphAt = (from: Vec[], to: Vec[], p: number) =>
	from.map((a, i) => `${lerp(a.x, to[i].x, p)},${lerp(a.y, to[i].y, p)}`).join(' ');
