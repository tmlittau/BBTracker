// Pure training math, mirrored from the backend services so the UI can show
// live estimates without a round-trip. Keep in sync with apps/training/services.py.

/** Estimated 1RM via Epley: weight * (1 + reps/30). Null if not applicable. */
export function estimated1rm(weight: number | null, reps: number | null): number | null {
	if (weight == null || reps == null) return null;
	if (weight <= 0 || reps <= 0 || reps > 30) return null;
	if (reps === 1) return round2(weight);
	return round2(weight * (1 + reps / 30));
}

export function round2(n: number): number {
	return Math.round(n * 100) / 100;
}

const WARMUP = 'warmup';

/** Tonnage for a single set; 0 for warm-ups or missing data. */
export function setVolume(
	weight: number | null,
	reps: number | null,
	setType: string
): number {
	if (setType === WARMUP || weight == null || reps == null) return 0;
	return round2(weight * reps);
}

export interface PlateResult {
	/** Plates for ONE side of the bar, largest first. */
	perSide: number[];
	/** Weight actually achievable with the given plates (<= target). */
	achievable: number;
	/** Leftover that couldn't be matched (target - achievable). */
	remainder: number;
}

/** Default rest (seconds) for a set type: 120 for working sets, 0 otherwise. */
export function defaultRestSeconds(setType: string): number {
	return setType === 'working' ? 120 : 0;
}

export type UnitSystem = 'metric' | 'imperial';

/** Weight unit label for a unit system. */
export function weightUnit(unit: UnitSystem): string {
	return unit === 'imperial' ? 'lb' : 'kg';
}

/** Standard Olympic bar weight (kg / lb). */
export function barWeight(unit: UnitSystem): number {
	return unit === 'imperial' ? 45 : 20;
}

// Standard per-side plate denominations. Metric's "one plate" is 20 kg (not 25);
// imperial's is 45 lb.
const PLATES: Record<UnitSystem, number[]> = {
	metric: [20, 15, 10, 5, 2.5, 1.25],
	imperial: [45, 35, 25, 10, 5, 2.5]
};

/**
 * Plate calculator: which plates per side to load a barbell to `target`, using the
 * standard bar + plate set for the unit system. Greedy — correct for standard sets.
 */
export function platesPerSide(target: number, unit: UnitSystem = 'metric'): PlateResult {
	const bar = barWeight(unit);
	const perSide: number[] = [];
	if (target <= bar) {
		return { perSide, achievable: bar, remainder: round2(Math.max(0, target - bar)) };
	}
	let remaining = (target - bar) / 2;
	for (const plate of PLATES[unit]) {
		while (remaining >= plate - 1e-9) {
			perSide.push(plate);
			remaining = round2(remaining - plate);
		}
	}
	const achievable = round2(bar + 2 * perSide.reduce((s, p) => s + p, 0));
	return { perSide, achievable, remainder: round2(target - achievable) };
}

/** Format seconds as m:ss for the rest timer. */
export function formatDuration(totalSeconds: number): string {
	const s = Math.max(0, Math.floor(totalSeconds));
	const m = Math.floor(s / 60);
	const rem = s % 60;
	return `${m}:${rem.toString().padStart(2, '0')}`;
}

/** Compact workout length, e.g. "45m" or "1h 23m". */
export function formatHM(totalSeconds: number): string {
	const s = Math.max(0, Math.floor(totalSeconds));
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** Live workout clock: "M:SS" under an hour, "H:MM:SS" beyond. */
export function formatClock(totalSeconds: number): string {
	const s = Math.max(0, Math.floor(totalSeconds));
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const ss = (s % 60).toString().padStart(2, '0');
	return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

/** Whole seconds between two ISO timestamps (0 if end precedes start). */
export function durationSeconds(startISO: string, endISO: string | null): number {
	if (!endISO) return 0;
	return Math.max(0, Math.floor((new Date(endISO).getTime() - new Date(startISO).getTime()) / 1000));
}
