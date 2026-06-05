// Pure protocol helpers for live UI math, mirrored from apps/protocols/services.py.

/** Fraction of a dose still present after `hours` (exponential decay). */
export function remainingFraction(hours: number, halfLifeHours: number | null): number {
	if (!halfLifeHours || halfLifeHours <= 0) return 0;
	if (hours <= 0) return 1;
	return 0.5 ** (hours / halfLifeHours);
}

/** Active drug remaining from one dose: amount × ester-fraction × decay. */
export function activeAmount(
	amount: number,
	activeFraction: number,
	hours: number,
	halfLifeHours: number | null
): number {
	return amount * activeFraction * remainingFraction(hours, halfLifeHours);
}

export type SiteStatus = 'rested' | 'recovering' | 'fresh';

/** Recency bucket for an injection site (matches backend thresholds). */
export function siteStatus(daysSince: number | null): SiteStatus {
	if (daysSince == null || daysSince >= 7) return 'rested';
	if (daysSince >= 3) return 'recovering';
	return 'fresh';
}

export const SITE_COLORS: Record<SiteStatus, string> = {
	rested: '#16a34a', // green-600 — good to use
	recovering: '#f59e0b', // amber-500
	fresh: '#dc2626' // red-600 — used recently, let it recover
};

export type MarkerFlag = 'low' | 'in_range' | 'high';

export function markerFlag(
	value: number,
	low: number | null,
	high: number | null
): MarkerFlag {
	if (low != null && value < low) return 'low';
	if (high != null && value > high) return 'high';
	return 'in_range';
}

export function num(value: string | number | null | undefined): number {
	if (value == null) return 0;
	return typeof value === 'number' ? value : parseFloat(value) || 0;
}

/** Concentration in `mg` weeks from a weekly dose at steady state (informational). */
export function weeklyToDaily(perWeek: number): number {
	return perWeek / 7;
}
