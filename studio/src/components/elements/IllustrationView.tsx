import React, {useId} from 'react';
import {Img} from 'remotion';
import {resolveAsset} from '../../lib/assets';
import {easeInOut, progress} from '../../lib/math';
import {SvgImage} from '../SvgImage';
import type {ImageElement} from '../../types';
import type {ElProps} from './index';

/** The mask colors only locally scheduled regions. Pen lines are real path elements. */
export const IllustrationView: React.FC<ElProps<ImageElement>> = ({r, t, ctx}) => {
	const {el, geom} = r;
	const {w, h, ox, oy} = geom.box;
	const src = resolveAsset(ctx.videoId, el.src);
	const id = useId().replace(/[^\w-]/g, '');
	const regions = el.illustration!.regions;
	const done = regions.every((region) => t >= region.end);
	const style = {position: 'absolute' as const, left: ox, top: oy, width: w, height: h};
	if (done) return <Img src={src} style={style} data-illustration-final />;
	return (
		<svg width={w} height={h} viewBox="0 0 1 1" preserveAspectRatio="none" style={style} data-illustration-regions>
			<defs>
				<mask id={id} x={0} y={0} width={1} height={1} maskUnits="userSpaceOnUse"
					maskContentUnits="userSpaceOnUse" style={{maskType: 'alpha'}}>
					{regions.map((region, i) => (
						<path key={i} d={region.d} fill="white" fillRule="evenodd"
							opacity={easeInOut(progress(t, region.at, region.end - region.at))} />
					))}
				</mask>
			</defs>
			<SvgImage href={src} width={1} height={1} preserveAspectRatio="none" mask={`url(#${id})`} />
		</svg>
	);
};
