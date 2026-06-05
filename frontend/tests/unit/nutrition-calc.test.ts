import { describe, expect, it } from 'vitest';
import { barWidth, kcalFromMacros, macroColor, microColor, num, pct } from '../../src/lib/nutrition/calc';

describe('kcalFromMacros', () => {
	it('applies 4/4/9 factors', () => {
		expect(kcalFromMacros(180, 200, 60)).toBe(180 * 4 + 200 * 4 + 60 * 9);
	});
	it('is zero for nothing', () => {
		expect(kcalFromMacros(0, 0, 0)).toBe(0);
	});
});

describe('pct', () => {
	it('computes whole percent', () => {
		expect(pct(62, 180)).toBe(34);
		expect(pct(100, 100)).toBe(100);
	});
	it('returns null without a target', () => {
		expect(pct(50, 0)).toBeNull();
		expect(pct(50, null)).toBeNull();
	});
});

describe('barWidth', () => {
	it('clamps to 0–100', () => {
		expect(barWidth(150)).toBe(100);
		expect(barWidth(-10)).toBe(0);
		expect(barWidth(42)).toBe(42);
		expect(barWidth(null)).toBe(0);
	});
});

describe('microColor', () => {
	it('greens at/above target, ambers mid, reds low', () => {
		expect(microColor(120)).toBe('green');
		expect(microColor(100)).toBe('green');
		expect(microColor(60)).toBe('amber');
		expect(microColor(20)).toBe('red');
		expect(microColor(null)).toBe('none');
	});
});

describe('macroColor', () => {
	it('greens on-track, ambers near, reds far/over', () => {
		expect(macroColor(100)).toBe('green');
		expect(macroColor(118)).toBe('amber');
		expect(macroColor(70)).toBe('amber');
		expect(macroColor(160)).toBe('red');
		expect(macroColor(30)).toBe('red');
		expect(macroColor(null)).toBe('none');
	});
});

describe('num', () => {
	it('coerces strings and nullish', () => {
		expect(num('12.5')).toBe(12.5);
		expect(num(7)).toBe(7);
		expect(num(null)).toBe(0);
		expect(num('')).toBe(0);
	});
});
