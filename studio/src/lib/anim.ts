// Trạng thái animation của 1 element tại thời điểm t (giây tuyệt đối). Hàm thuần.
import {spring} from 'remotion';
import type {FadeCurve, PenTravel, Vec} from '../types';
import {clamp, easeDraw, easeIn, easeInOut, easeOut, lerp, progress} from './math';
import type {Resolved} from './resolve';

export interface ElementState {
	visible: boolean;
	/** điểm neo sau moves (toạ độ scene) */
	x: number;
	y: number;
	dx: number;
	dy: number;
	scale: number;
	rotate: number;
	rotateY: number;
	opacity: number;
	/** tiến độ vẽ 0..1 khi enter = draw, null nếu không vẽ */
	draw: number | null;
	grayscale: number;
}

const SLIDE = 60;

// Spring êm: overshoot rất nhỏ (<4% trên khoảng 0.85→1)
const POP_SPRING = {damping: 18, stiffness: 180, mass: 1};

const fadeAt = (p: number, curve?: FadeCurve) => {
	switch (curve) {
		case 'linear': return p;
		case 'ease-in': return easeIn(p);
		case 'ease-out': return easeOut(p);
		default: return easeInOut(p);
	}
};

export const computeState = (r: Resolved, t: number, fps: number): ElementState => {
	const {el, geom} = r;
	const s: ElementState = {
		visible: true,
		x: geom.anchor.x,
		y: geom.anchor.y,
		dx: 0,
		dy: 0,
		scale: el.scale ?? 1,
		rotate: el.rotate ?? 0,
		rotateY: 0,
		opacity: el.opacity ?? 1,
		draw: null,
		grayscale: 0,
	};

	// --- moves (tích luỹ, easeInOut) ---
	if (el.moves && el.moves.length) {
		const ms = [...el.moves].sort((a, b) => a.at - b.at);
		const isPath = el.type === 'path';
		for (const m of ms) {
			if (t < m.at) break;
			const p = easeInOut(progress(t, m.at, m.duration ?? 0.6));
			// path: x/y của move là độ lệch so với vị trí gốc
			if (m.x !== undefined) s.x = lerp(s.x, isPath ? geom.anchor.x + m.x : m.x, p);
			if (m.y !== undefined) s.y = lerp(s.y, isPath ? geom.anchor.y + m.y : m.y, p);
			if (m.scale !== undefined) s.scale = lerp(s.scale, m.scale, p);
			if (m.rotate !== undefined) s.rotate = lerp(s.rotate, m.rotate, p);
			if (m.opacity !== undefined) s.opacity = lerp(s.opacity, m.opacity, p);
		}
	}

	// --- enter ---
	if (t < r.enterAt) {
		s.visible = false;
		return s;
	}
	const e = t - r.enterAt;
	const p = progress(t, r.enterAt, r.enterDur);
	const flip = el.type === 'card' && el.flipIn;
	if (flip) {
		s.rotateY = 90 * (1 - easeOut(p));
		s.opacity *= clamp(p * 4, 0, 1);
		if (r.enter === 'pop') s.scale *= 0.92 + 0.08 * easeOut(p);
	} else {
		switch (r.enter) {
			case 'pop': {
				const sp = spring({
					frame: e * fps,
					fps,
					config: POP_SPRING,
					durationInFrames: Math.max(1, r.enterDur * fps),
				});
				s.scale *= 0.85 + 0.15 * sp;
				s.opacity *= easeOut(clamp(p / 0.6, 0, 1));
				break;
			}
			case 'slide': {
				const offset = el.enterOffset ?? {x: -SLIDE, y: 0};
				s.dx += offset.x * (1 - easeOut(p));
				s.dy += offset.y * (1 - easeOut(p));
				break;
			}
			case 'rotate':
				s.rotate += (el.enterAngle ?? -180) * (1 - easeInOut(p));
				break;
			case 'slide-up':
				s.dy += SLIDE * (1 - easeOut(p));
				s.opacity *= easeOut(clamp(p / 0.7, 0, 1));
				break;
			case 'slide-left':
				s.dx += SLIDE * (1 - easeOut(p));
				s.opacity *= easeOut(clamp(p / 0.7, 0, 1));
				break;
			case 'slide-right':
				s.dx -= SLIDE * (1 - easeOut(p));
				s.opacity *= easeOut(clamp(p / 0.7, 0, 1));
				break;
			case 'fade':
				s.opacity *= fadeAt(p, el.enterCurve);
				break;
			case 'grow':
				// bar tự mọc chiều cao; các loại khác phóng to từ 0
				if (el.type !== 'bar') s.scale *= lerp(el.enterScale ?? 0, 1, easeOut(p));
				s.opacity *= clamp(p * 3, 0, 1);
				break;
			case 'draw':
				// trace map: tuyến tính để tốc độ bút đều
				s.draw = el.type === 'image' && el.trace && geom.trace ? p : easeDraw(p);
				break;
			case 'none':
				break;
		}
	}

	// --- grayscale (ảnh "phủ bụi") ---
	if (el.type === 'image' && el.grayscale) {
		const g = el.grayscale;
		s.grayscale = clamp(g.to, 0, 1) * easeInOut(progress(t, g.at, g.duration ?? 0.8));
	}

	// --- exit ---
	if (r.exitAt !== null && t >= r.exitAt) {
		const q = progress(t, r.exitAt, r.exitDur);
		if (r.exit === 'none' || q >= 1) {
			s.visible = false;
			return s;
		}
		switch (r.exit) {
			case 'fade':
				s.opacity *= 1 - fadeAt(q, el.exitCurve);
				break;
			case 'slide-down':
				s.dy += SLIDE * easeIn(q);
				s.opacity *= 1 - easeIn(q);
				break;
			case 'shrink':
				s.scale *= 1 - 0.4 * easeIn(q);
				s.opacity *= 1 - easeIn(q);
				break;
		}
	}
	// --- idle: rung rung liên tục khi đang hiện (nhân vật hoạt hình, plan/16) ---
	if (el.idle?.type === 'rung' && s.visible && s.opacity > 0.001) {
		const amp = el.idle.amplitude ?? 2.5;
		const hz = el.idle.speed ?? 1.6;
		const w = t * hz * Math.PI * 2;
		s.rotate += Math.sin(w) * amp;
		if (el.idle.scaleAmp) s.scale *= 1 + Math.sin(w + Math.PI / 2) * el.idle.scaleAmp;
	}

	if (el.zoom) {
		const {at, in: zoomIn, hold = 0, out, scale, origin = {x: 0, y: 0}} = el.zoom;
		const amount = easeInOut(progress(t, at, zoomIn)) * (1 - easeInOut(progress(t, at + zoomIn + hold, out)));
		const factor = lerp(1, scale, amount);
		const pivot = toScene(s, origin);
		s.dx += (pivot.x - s.x - s.dx) * (1 - factor);
		s.dy += (pivot.y - s.y - s.dy) * (1 - factor);
		s.scale *= factor;
	}

	if (el.type === 'path' && el.inkFade)
		s.opacity *= 1 - easeInOut(progress(t, el.inkFade.at, el.inkFade.end - el.inkFade.at));

	if (s.opacity <= 0.001) s.visible = false;
	return s;
};

/** Biến điểm local (so với neo) sang toạ độ scene theo state hiện tại */
export const toScene = (s: ElementState, local: Vec): Vec => {
	const a = (s.rotate * Math.PI) / 180;
	const lx = local.x * s.scale;
	const ly = local.y * s.scale;
	return {
		x: s.x + s.dx + lx * Math.cos(a) - ly * Math.sin(a),
		y: s.y + s.dy + lx * Math.sin(a) + ly * Math.cos(a),
	};
};

export interface HandPose {
	lift?: number;
	x: number;
	y: number;
	opacity: number;
	active: boolean;
	startedAt: number;
}

const LEAD = 0.3;
const TAIL = 0.4;

/** Vị trí tay vẽ (toạ độ scene) hoặc null nếu không hiện tay */
export const handPose = (r: Resolved, s: ElementState, t: number): HandPose | null => {
	if (!r.hand || r.enter !== 'draw') return null;
	const t0 = r.enterAt;
	const t1 = r.enterAt + r.enterDur;
	if (t < t0 - LEAD || t > t1 + TAIL) return null;
	if (r.exitAt !== null && t >= r.exitAt) return null;
	const p = t < t0 ? 0 : t > t1 ? 1 : (s.draw ?? 1);
	const tip = toScene({...s, visible: true}, r.geom.tipAt(p));
	let k = 0;
	let off = {x: 0, y: 0};
	if (t < t0) {
		k = (t0 - t) / LEAD;
		const e = easeIn(k);
		off = {x: 160 * e, y: 220 * e};
	} else if (t > t1) {
		k = (t - t1) / TAIL;
		const e = easeIn(k);
		off = {x: 220 * e, y: 260 * e};
	}
	// tay giữ đậm khi rút ra, chỉ mờ ở đoạn cuối
	const op = t < t0 ? 1 - Math.pow(clamp(k, 0, 1), 2) : 1 - Math.pow(clamp(k, 0, 1), 3);
	return {x: tip.x + off.x, y: tip.y + off.y, opacity: op, active: t >= t0 && t <= t1, startedAt: t0};
};

/**
 * Chỉ giữ MỘT bàn tay: ưu tiên element đang vẽ bắt đầu muộn nhất;
 * nếu không có element nào đang vẽ thì lấy pose vào/ra gần nhất.
 */
export const pickHand = (poses: HandPose[]): HandPose | null => {
	if (poses.length === 0) return null;
	const active = poses.filter((p) => p.active);
	const pool = active.length ? active : poses;
	return pool.reduce((a, b) => (b.startedAt > a.startedAt ? b : a));
};

const carryGrip = (state: ElementState, local: Vec): Vec => {
	// Match the precision and order of the element's CSS transform, including a card flip.
	const a = Number(state.rotateY.toFixed(2)) * Math.PI / 180;
	const perspective = 1400 / (1400 + local.x * Math.sin(a));
	return toScene({
		...state,
		dx: Number(state.dx.toFixed(2)),
		dy: Number(state.dy.toFixed(2)),
		scale: Number(state.scale.toFixed(4)),
	}, {x: local.x * Math.cos(a) * perspective, y: local.y * perspective});
};

export interface CarryHandPose extends Vec {
	closed: number;
	rotate: number;
	phase: 'approach' | 'grip' | 'carry' | 'release' | 'exit';
}

/** The element and its bearing hand are sampled together, with no state from previous frames. */
export const animateCarry = (r: Resolved, t: number, fps: number, base = computeState(r, t, fps)):
	{state: ElementState; hand: CarryHandPose | null} => {
	const c = r.el.carry;
	if (!c || t < c.start) return {state: base, hand: null};
	const between = (a: number, b: number) => easeInOut(progress(t, a, b - a));
	const state = {...base};
	const drag = c.mode === 'drag';
	if (t >= c.pickup) {
		const start = computeState(r, c.pickup, fps);
		const p = between(c.pickup, c.land);
		state.x = lerp(start.x + Number(start.dx.toFixed(2)), c.target.x, p);
		state.y = lerp(start.y + Number(start.dy.toFixed(2)), c.target.y, p) - (drag ? 0 : (c.lift ?? 95)) * 4 * p * (1 - p);
		state.dx = 0;
		state.dy = 0;
	}
	if (t >= c.end || (t < c.release && !state.visible)) return {state, hand: null};

	const grip = carryGrip(state, c.grip);
	const pose = (phase: CarryHandPose['phase'], closed: number, rotate: number, point = grip) =>
		({state, hand: {...point, phase, closed: drag ? 0 : closed, rotate: drag ? 0 : rotate}});
	const mix = (from: Vec, to: Vec, p: number): Vec =>
		({x: lerp(from.x, to.x, p), y: lerp(from.y, to.y, p)});
	if (t < c.contact) {
		const p = between(c.start, c.contact);
		return pose('approach', 0, lerp(-12, -3, p), mix(c.from, grip, p));
	}
	if (t < c.pickup) {
		const p = between(c.contact, c.pickup);
		return pose('grip', p, lerp(-3, 0, p));
	}
	if (t < c.land) {
		const p = between(c.pickup, c.land);
		return pose('carry', 1, -8 * Math.sin(Math.PI * p));
	}
	if (t < c.release) {
		const p = between(c.land, c.release);
		return pose('release', 1 - p, 4 * p);
	}
	const p = between(c.release, c.end);
	const atRelease = {...computeState(r, c.release, fps), ...c.target, dx: 0, dy: 0};
	return pose('exit', 0, lerp(4, 18, p), mix(carryGrip(atRelease, c.grip), c.to, p));
};

type AnimatedItem = {r: Resolved; state: ElementState; hand: CarryHandPose | null};

const travelPen = (items: AnimatedItem[], travel: PenTravel, t: number, fps: number): HandPose | null => {
	if (t < travel.start || t >= travel.end) return null;
	const strokes = items.filter(({r}) => r.el.hand === true && r.enter === 'draw' && (r.el.type === 'path' || (r.el.type === 'image' && r.el.reveal)))
		.sort((a, b) => a.r.enterAt - b.r.enterAt);
	if (!strokes.length) return null;

	const tipAt = ({r, state}: AnimatedItem, p: number, at: number): Vec => {
		const path = r.geom.path;
		const tip = path?.exactPointAt(path.length * p);
		const local = path && tip
			? {x: tip.x - path.bbox.x - path.bbox.w / 2, y: tip.y - path.bbox.y - path.bbox.h / 2}
			: r.geom.tipAt(p);
		return carryGrip(at === t ? state : computeState(r, at, fps), local);
	};

	let previous = travel.from;
	let previousEnd = travel.start;
	const moveTo = (next: Vec, at: number): HandPose => {
		const p = easeInOut(progress(t, previousEnd, at - previousEnd));
		return {x: lerp(previous.x, next.x, p), y: lerp(previous.y, next.y, p),
			opacity: 1, active: false, startedAt: travel.start,
			lift: travel.lift ? Math.sin(Math.PI * p) : undefined};
	};
	for (const stroke of strokes) {
		const start = stroke.r.enterAt;
		const end = start + stroke.r.enterDur;
		if (t < start) return moveTo(tipAt(stroke, 0, start), start);
		if (t <= end) return {...tipAt(stroke, stroke.state.draw ?? 1, t), opacity: 1, active: true, startedAt: start};
		previous = tipAt(stroke, 1, end);
		previousEnd = end;
	}
	return moveTo(travel.to, travel.end);
};

/** One frame sample drives the drawing, any attached object, and the scene's only hand. */
export const sampleSceneAnimation = (resolved: Resolved[], t: number, fps: number, penTravel?: PenTravel) => {
	const items = resolved.map((r, i) => ({r, i, ...animateCarry(r, t, fps)}))
		.sort((a, b) => (a.r.el.z ?? 0) - (b.r.el.z ?? 0) || a.i - b.i);
	const carry = items.find((item) => item.hand)?.hand;
	if (carry) return {items, hand: {kind: 'carry' as const, pose: carry}};
	const pose = penTravel ? travelPen(items, penTravel, t, fps)
		: pickHand(items.map(({r, state}) => handPose(r, state, t)).filter((p): p is HandPose => p !== null));
	return {items, hand: {kind: 'draw' as const, pose}};
};
