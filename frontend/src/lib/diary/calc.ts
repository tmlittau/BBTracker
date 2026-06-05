// Small pure helpers for the diary UI.

export function todayISO(): string {
	return new Date().toISOString().slice(0, 10);
}

/** Average of the 1–5 subjective scores present on a check-in (null if none). */
export function wellbeingAverage(
	scores: (number | null | undefined)[]
): number | null {
	const present = scores.filter((s): s is number => typeof s === 'number');
	if (present.length === 0) return null;
	return Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 10) / 10;
}

/** Colour for a 1–5 score. Soreness is inverted (high = bad). */
export function scoreColor(value: number | null, inverted = false): string {
	if (value == null) return 'bg-neutral-700';
	const v = inverted ? 6 - value : value;
	if (v >= 4) return 'bg-green-600';
	if (v >= 3) return 'bg-amber-500';
	return 'bg-red-600';
}

export function num(value: string | number | null | undefined): number {
	if (value == null) return 0;
	return typeof value === 'number' ? value : parseFloat(value) || 0;
}
