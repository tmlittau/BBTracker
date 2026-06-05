import { describe, expect, it } from 'vitest';
import {
	activeAmount,
	markerFlag,
	remainingFraction,
	siteStatus
} from '../../src/lib/protocols/calc';

describe('remainingFraction', () => {
	it('is full at t=0 and halves each half-life', () => {
		expect(remainingFraction(0, 24)).toBe(1);
		expect(remainingFraction(24, 24)).toBe(0.5);
		expect(remainingFraction(48, 24)).toBe(0.25);
	});
	it('is zero without a half-life', () => {
		expect(remainingFraction(10, 0)).toBe(0);
		expect(remainingFraction(10, null)).toBe(0);
	});
});

describe('activeAmount', () => {
	it('applies ester fraction and decay', () => {
		expect(activeAmount(100, 0.7, 0, 24)).toBeCloseTo(70);
		expect(activeAmount(100, 1, 24, 24)).toBeCloseTo(50);
	});
});

describe('siteStatus', () => {
	it('buckets by days since last use', () => {
		expect(siteStatus(null)).toBe('rested');
		expect(siteStatus(7)).toBe('rested');
		expect(siteStatus(4)).toBe('recovering');
		expect(siteStatus(1)).toBe('fresh');
	});
});

describe('markerFlag', () => {
	it('flags low/high/in-range', () => {
		expect(markerFlag(250, 300, 1000)).toBe('low');
		expect(markerFlag(650, 300, 1000)).toBe('in_range');
		expect(markerFlag(1200, 300, 1000)).toBe('high');
		expect(markerFlag(5, null, null)).toBe('in_range');
	});
});
