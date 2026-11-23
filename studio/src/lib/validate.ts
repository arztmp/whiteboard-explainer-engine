import type {Timeline, TimelineElement, Vec} from '../types';

const ELEMENT_TYPES = ['morph', 'image', 'text', 'counter', 'card', 'bar', 'path', 'rect', 'circle', 'clock', 'caption'];
const ENTERS = ['slide', 'rotate', 'pop', 'slide-up', 'slide-left', 'slide-right', 'fade', 'draw', 'grow', 'none'];
const EXITS = ['fade', 'slide-down', 'shrink', 'none'];
const TRANSITIONS = ['none', 'fade', 'push-left', 'push-up', 'zoom-from', 'pan'];

const REQUIRED: Record<string, string[]> = {
	image: ['src', 'w', 'x', 'y'],
	morph: ['x', 'y', 'from', 'to', 'at', 'duration'],
	text: ['text', 'x', 'y'],
	counter: ['from', 'to', 'x', 'y'],
	card: ['w', 'h', 'x', 'y'],
	bar: ['w', 'maxH', 'value', 'x', 'y'],
	path: ['d'],
	rect: ['x', 'y'],
	circle: ['x', 'y'],
	clock: ['r', 'fromHour', 'toHour', 'x', 'y'],
	caption: ['words', 'x', 'y'],
};

const validPoint = (point: Vec | undefined) => point && Number.isFinite(point.x) && Number.isFinite(point.y);

/** Kiểm tra nhẹ timeline, trả về danh sách lỗi (rỗng = hợp lệ) */
export const validateTimeline = (tl: Timeline): string[] => {
	const errs: string[] = [];
	if (!tl || typeof tl !== 'object') return ['timeline không phải object'];
	if (!['A', 'B', 'C'].includes(tl.style)) errs.push(`style không hợp lệ: ${tl.style}`);
	if (!(tl.duration > 0)) errs.push('duration phải > 0');
	if (!Array.isArray(tl.scenes) || tl.scenes.length === 0) errs.push('scenes rỗng');
	if (tl.hand && (!tl.hand.src || !tl.hand.tip)) errs.push('hand cần src và tip');
	if (tl.rough !== undefined && typeof tl.rough !== 'boolean') errs.push(`rough phải là boolean (${String(tl.rough)})`);
	if (tl.fitText !== undefined && typeof tl.fitText !== 'boolean')
		errs.push(`fitText phải là boolean (${String(tl.fitText)})`);
	if (tl.roughness !== undefined && !(typeof tl.roughness === 'number' && tl.roughness >= 0))
		errs.push(`roughness phải là số ≥ 0 (${String(tl.roughness)})`);
	if (tl.bowing !== undefined && !(typeof tl.bowing === 'number' && Number.isFinite(tl.bowing)))
		errs.push(`bowing phải là số (${String(tl.bowing)})`);
	const carryHand = tl.carryHand;
	if (carryHand) {
		const {src, tip, scale, grid} = carryHand;
		if (typeof src !== 'string' || !src || !validPoint(tip) ||
			(scale !== undefined && (!Number.isFinite(scale) || scale <= 0)))
			errs.push('carryHand requires src, a finite tip and a positive scale');
		if (grid && ![grid.columns, grid.rows].every((n) => Number.isInteger(n) && n > 0))
			errs.push('carryHand.grid requires positive integer columns and rows');
	}
	const ids = new Set<string>();
	(tl.scenes ?? []).forEach((s, si) => {
		const where = `scenes[${si}](${s.id})`;
		if (!s.id) errs.push(`${where}: thiếu id`);
		if (typeof s.start !== 'number' || typeof s.end !== 'number') errs.push(`${where}: thiếu start/end`);
		if (s.transitionIn && !TRANSITIONS.includes(s.transitionIn.type))
			errs.push(`${where}: transitionIn.type không hợp lệ (${s.transitionIn.type})`);
		if (s.transitionIn?.type === 'zoom-from' && si > 0) {
			const prev = tl.scenes[si - 1];
			if (s.transitionIn.fromElement && !prev.elements.some((e) => e.id === s.transitionIn!.fromElement))
				errs.push(`${where}: fromElement "${s.transitionIn.fromElement}" không có ở scene trước`);
		}
		const travel = s.penTravel;
		if (travel) {
			if (!tl.hand || !validPoint(travel.from) || !validPoint(travel.to) ||
				!Number.isFinite(travel.start) || !Number.isFinite(travel.end) ||
				(travel.scale !== undefined && (!Number.isFinite(travel.scale) || travel.scale <= 0)) ||
				travel.start < s.start || travel.end > s.end || travel.end > tl.duration || travel.start >= travel.end)
				errs.push(`${where}: penTravel requires a hand, finite endpoints and a time range inside the scene`);
			const strokes = (s.elements ?? []).filter((e) => e.hand).sort((a, b) => (a.enterAt ?? 0) - (b.enterAt ?? 0));
			if (!strokes.length) errs.push(`${where}: penTravel requires at least one pen stroke`);
			let previousEnd = travel.start;
			for (const stroke of strokes) {
				const {enterAt, enterDuration} = stroke;
				const validPath = stroke.type === 'path' && !(stroke.rough ?? tl.rough) &&
					!stroke.dashed && !stroke.arrow && !stroke.fill;
				const validReveal = stroke.type === 'image' && !!stroke.reveal;
				if ((!validPath && !validReveal) || stroke.enter !== 'draw' || stroke.exitAt != null) {
					errs.push(`${where}: penTravel stroke "${stroke.id}" must be a plain drawn path or image reveal`);
					continue;
				}
				if (enterAt == null || enterDuration == null || !Number.isFinite(enterAt) ||
					!Number.isFinite(enterDuration) || enterDuration <= 0 ||
					enterAt <= previousEnd || enterAt + enterDuration >= travel.end) {
					errs.push(`${where}: penTravel stroke "${stroke.id}" needs time for pen repositioning`);
					continue;
				}
				previousEnd = enterAt + enterDuration;
			}
		}
		const carries: {start: number; end: number; id: string}[] = [];
		(s.elements ?? []).forEach((e: TimelineElement, ei) => {
			const w = `${where}.elements[${ei}](${e.id})`;
			if (!e.id) errs.push(`${w}: thiếu id`);
			else if (ids.has(e.id)) errs.push(`${w}: id trùng "${e.id}"`);
			ids.add(e.id);
			if (!ELEMENT_TYPES.includes(e.type)) {
				errs.push(`${w}: type không hợp lệ (${(e as {type: string}).type})`);
				return;
			}
			for (const k of REQUIRED[e.type]) {
				if ((e as unknown as Record<string, unknown>)[k] === undefined) errs.push(`${w}: thiếu "${k}"`);
			}
			if (e.enter && !ENTERS.includes(e.enter)) errs.push(`${w}: enter không hợp lệ (${e.enter})`);
			if (e.exit && !EXITS.includes(e.exit)) errs.push(`${w}: exit không hợp lệ (${e.exit})`);
			if (e.type === 'bar' && e.horizontal !== undefined && typeof e.horizontal !== 'boolean')
				errs.push(`${w}: horizontal phải là boolean (${String(e.horizontal)})`);
			const ex = e as unknown as Record<string, unknown>;
			for (const k of ['rough', 'fit']) {
				if (ex[k] !== undefined && typeof ex[k] !== 'boolean') errs.push(`${w}: ${k} phải là boolean (${String(ex[k])})`);
			}
			if (ex.maxLines !== undefined && !(Number.isInteger(ex.maxLines) && (ex.maxLines as number) >= 1))
				errs.push(`${w}: maxLines phải là số nguyên ≥ 1 (${String(ex.maxLines)})`);
			if (e.type === 'text' && ex.mark !== undefined && !['khoanh', 'gach_chan'].includes(ex.mark as string))
				errs.push(`${w}: mark phải là "khoanh" hoặc "gach_chan" (${String(ex.mark)})`);
			const positive = (n: number) => Number.isFinite(n) && n > 0;
			if (e.type === 'morph' && (!Array.isArray(e.from) || !Array.isArray(e.to) ||
				e.from.length < 3 || e.from.length !== e.to.length ||
				![...e.from, ...e.to].every(validPoint) || !positive(e.duration) || !Number.isFinite(e.at)))
				errs.push(`${w}: morph needs equally sized finite contours and a positive duration`);
			if (e.type === 'image') {
				const {reveal, scatter} = e;
				if (reveal && (scatter || e.trace || e.video || e.enter !== 'draw' ||
					(reveal.rows !== undefined && (!Number.isInteger(reveal.rows) || !positive(reveal.rows)))))
					errs.push(`${w}: reveal requires draw and a positive row count`);
				if (scatter && (e.video || e.trace || e.flipX || !Number.isFinite(scatter.at) ||
					!positive(scatter.out) || !positive(scatter.back) || !Number.isFinite(scatter.hold ?? 0) ||
					(scatter.hold ?? 0) < 0 || (scatter.returnDirection && !(scatter.hold && scatter.hold > 0)) ||
					![scatter.columns ?? 12, scatter.rows ?? 8].every((n) => Number.isInteger(n) && n >= 1 && n <= 30) ||
					[scatter.direction, scatter.returnDirection].some((v) => v !== undefined && !validPoint(v))))
					errs.push(`${w}: invalid scatter timing, grid or directions`);
			}
			if (e.zoom && (!Number.isFinite(e.zoom.at) || !positive(e.zoom.in) || !positive(e.zoom.out) ||
				!positive(e.zoom.scale) || !Number.isFinite(e.zoom.hold ?? 0) || (e.zoom.hold ?? 0) < 0 ||
				(e.zoom.origin && !validPoint(e.zoom.origin))))
				errs.push(`${w}: invalid zoom timing, scale or origin`);

			if (e.carry) {
				const c = e.carry;
				if (c.mode !== undefined && c.mode !== 'carry' && c.mode !== 'drag')
					errs.push(`${w}: carry.mode must be "carry" or "drag"`);
				const times = [c.start, c.contact, c.pickup, c.land, c.release, c.end];
				if (!tl.carryHand) errs.push(`${w}: carry requires timeline.carryHand`);
				if (![c.grip, c.target, c.from, c.to].every(validPoint))
					errs.push(`${w}: carry requires finite grip, target, from and to points`);
				if (!times.every((at, i) => Number.isFinite(at) && (i === 0 || at > times[i - 1])) ||
					c.start < s.start || c.end > Math.min(s.end, tl.duration))
					errs.push(`${w}: carry timestamps must increase and fit within the scene`);
				if (c.lift !== undefined && (!Number.isFinite(c.lift) || c.lift < 0))
					errs.push(`${w}: carry.lift must be finite and nonnegative`);
				if (c.contact < (e.enterAt ?? s.start) || (e.exitAt != null && c.release > e.exitAt))
					errs.push(`${w}: the element must be on screen from contact to release`);
				carries.push({start: c.start, end: c.end, id: e.id});
			}
		});
		carries.sort((a, b) => a.start - b.start);
		for (let i = 1; i < carries.length; i++) {
			if (carries[i].start < carries[i - 1].end)
				errs.push(`${where}: overlapping carries for ${carries[i - 1].id} and ${carries[i].id}`);
		}
	});
	return errs;
};
