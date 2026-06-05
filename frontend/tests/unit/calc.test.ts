import { describe, expect, it } from 'vitest';
import { estimated1rm, formatDuration, platesPerSide, setVolume } from '../../src/lib/training/calc';

describe('estimated1rm', () => {
	it('returns the weight for a single rep', () => {
		expect(estimated1rm(100, 1)).toBe(100);
	});

	it('matches Epley for multi-rep sets', () => {
		expect(estimated1rm(100, 10)).toBe(133.33);
	});

	it('increases with weight and reps', () => {
		expect(estimated1rm(110, 5)!).toBeGreaterThan(estimated1rm(100, 5)!);
		expect(estimated1rm(100, 5)!).toBeGreaterThan(estimated1rm(100, 4)!);
	});

	it('rejects invalid input', () => {
		expect(estimated1rm(null, 5)).toBeNull();
		expect(estimated1rm(100, null)).toBeNull();
		expect(estimated1rm(0, 5)).toBeNull();
		expect(estimated1rm(100, 99)).toBeNull();
	});
});

describe('setVolume', () => {
	it('multiplies weight by reps for working sets', () => {
		expect(setVolume(100, 5, 'working')).toBe(500);
	});
	it('excludes warm-ups', () => {
		expect(setVolume(100, 5, 'warmup')).toBe(0);
	});
	it('is zero when data missing', () => {
		expect(setVolume(null, 5, 'working')).toBe(0);
	});
});

describe('platesPerSide', () => {
	it('computes plates for a standard 100kg load on a 20kg bar', () => {
		// (100 - 20) / 2 = 40 per side → 25 + 15
		const r = platesPerSide(100);
		expect(r.perSide).toEqual([25, 15]);
		expect(r.achievable).toBe(100);
		expect(r.remainder).toBe(0);
	});

	it('reports remainder when the target is not loadable', () => {
		const r = platesPerSide(101); // 40.5/side, smallest plate 1.25 → 40 loaded
		expect(r.achievable).toBe(100);
		expect(r.remainder).toBe(1);
	});

	it('returns just the bar when target <= bar', () => {
		const r = platesPerSide(20);
		expect(r.perSide).toEqual([]);
		expect(r.achievable).toBe(20);
	});
});

describe('formatDuration', () => {
	it('formats m:ss', () => {
		expect(formatDuration(0)).toBe('0:00');
		expect(formatDuration(9)).toBe('0:09');
		expect(formatDuration(75)).toBe('1:15');
		expect(formatDuration(600)).toBe('10:00');
	});
});
