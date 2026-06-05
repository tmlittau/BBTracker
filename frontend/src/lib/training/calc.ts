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

/**
 * Plate calculator: which plates per side to load a barbell to `target`.
 * `plates` are the denominations available (per side, any count). Greedy —
 * correct for standard gym plate sets.
 */
export function platesPerSide(
	target: number,
	barWeight = 20,
	plates: number[] = [25, 20, 15, 10, 5, 2.5, 1.25]
): PlateResult {
	const perSide: number[] = [];
	if (target <= barWeight) {
		return { perSide, achievable: barWeight, remainder: round2(Math.max(0, target - barWeight)) };
	}
	let remaining = (target - barWeight) / 2;
	const sorted = [...plates].sort((a, b) => b - a);
	for (const plate of sorted) {
		while (remaining >= plate - 1e-9) {
			perSide.push(plate);
			remaining = round2(remaining - plate);
		}
	}
	const achievable = round2(barWeight + 2 * perSide.reduce((s, p) => s + p, 0));
	return { perSide, achievable, remainder: round2(target - achievable) };
}

/** Format seconds as m:ss for the rest timer. */
export function formatDuration(totalSeconds: number): string {
	const s = Math.max(0, Math.floor(totalSeconds));
	const m = Math.floor(s / 60);
	const rem = s % 60;
	return `${m}:${rem.toString().padStart(2, '0')}`;
}
