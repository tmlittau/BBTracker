import { describe, expect, it } from 'vitest';
import { num, scoreColor, wellbeingAverage } from '../../src/lib/diary/calc';

describe('wellbeingAverage', () => {
	it('averages the present scores', () => {
		expect(wellbeingAverage([4, 3, 5, 4, 2])).toBe(3.6);
	});
	it('ignores null/undefined', () => {
		expect(wellbeingAverage([4, null, undefined, 2])).toBe(3);
	});
	it('is null when nothing present', () => {
		expect(wellbeingAverage([null, undefined])).toBeNull();
	});
});

describe('scoreColor', () => {
	it('greens high, reds low', () => {
		expect(scoreColor(5)).toBe('bg-green-600');
		expect(scoreColor(3)).toBe('bg-amber-500');
		expect(scoreColor(1)).toBe('bg-red-600');
		expect(scoreColor(null)).toBe('bg-neutral-700');
	});
	it('inverts soreness (5 = bad)', () => {
		expect(scoreColor(5, true)).toBe('bg-red-600');
		expect(scoreColor(1, true)).toBe('bg-green-600');
	});
});

describe('num', () => {
	it('coerces', () => {
		expect(num('84.5')).toBe(84.5);
		expect(num(null)).toBe(0);
	});
});
