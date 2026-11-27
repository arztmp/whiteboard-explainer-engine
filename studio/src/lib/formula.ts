import katex from 'katex';

const cache = new Map<string, string>();

export const formulaMarkup = (latex: string): string => {
	if (typeof latex !== 'string' || !latex.trim()) throw new Error('LaTeX must be a nonempty string');
	const cached = cache.get(latex);
	if (cached !== undefined) return cached;
	const markup = katex.renderToString(latex, {
		throwOnError: true,
		trust: false,
		output: 'htmlAndMathml',
		maxExpand: 1000,
		strict: (code) => code === 'unknownSymbol' ? 'error' : 'warn',
	});
	cache.set(latex, markup);
	return markup;
};
