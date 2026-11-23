import {fontFamily, fontsReady} from '../fonts';
import type {FontKind} from '../types';

export interface TextLine {
	text: string;
	width: number;
}

export interface TextLayout {
	lines: TextLine[];
	width: number;
	height: number;
	lineHeight: number;
}

let ctx: CanvasRenderingContext2D | null = null;
const cache = new Map<string, TextLayout>();

const getCtx = () => {
	if (!ctx && typeof document !== 'undefined') {
		ctx = document.createElement('canvas').getContext('2d');
	}
	return ctx;
};

export const measureWidth = (
	text: string,
	size: number,
	weight: number,
	font: FontKind,
): number => {
	const c = getCtx();
	if (!c) return text.length * size * 0.55;
	c.font = `${weight} ${size}px ${fontFamily(font)}`;
	return c.measureText(text).width;
};

/** Ngắt dòng tham lam theo maxWidth (đo bằng canvas, font đã nạp). '\n' = xuống dòng cứng. */
export const layoutText = (
	text: string,
	size: number,
	weight: number,
	font: FontKind,
	maxWidth: number | undefined,
	lineHeightMul: number,
	letterSpacing = 0,
): TextLayout => {
	const key = [text, size, weight, font, maxWidth ?? 0, lineHeightMul, letterSpacing].join('|');
	const hit = cache.get(key);
	if (hit) return hit;
	const lines: TextLine[] = [];
	const widthOf = (value: string) => measureWidth(value, size, weight, font) +
		Math.max(value.length - 1, 0) * letterSpacing;
	for (const para of text.split('\n')) {
		const words = para.split(/\s+/).filter(Boolean);
		if (words.length === 0) {
			lines.push({text: '', width: 0});
			continue;
		}
		let cur = words[0];
		for (let i = 1; i < words.length; i++) {
			const cand = `${cur} ${words[i]}`;
			if (maxWidth && widthOf(cand) > maxWidth) {
				lines.push({text: cur, width: widthOf(cur)});
				cur = words[i];
			} else {
				cur = cand;
			}
		}
		lines.push({text: cur, width: widthOf(cur)});
	}
	const lineHeight = size * lineHeightMul;
	const layout: TextLayout = {
		lines,
		width: Math.max(1, ...lines.map((l) => l.width)),
		height: lineHeight * lines.length,
		lineHeight,
	};
	// Chỉ cache khi font thật đã nạp, tránh giữ số đo của font fallback
	if (fontsReady()) cache.set(key, layout);
	return layout;
};
