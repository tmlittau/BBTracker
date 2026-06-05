// Pure nutrition helpers for live UI math. No framework deps.

/** Calories implied by macronutrient grams (4/4/9 Atwater factors). */
export function kcalFromMacros(protein: number, carb: number, fat: number): number {
	return Math.round(protein * 4 + carb * 4 + fat * 9);
}

/** Whole-percent of target, or null when there is no/zero target. */
export function pct(amount: number, target: number | null | undefined): number | null {
	if (!target) return null;
	return Math.round((amount / target) * 100);
}

/** Bar width clamped to 0–100 for a progress display. */
export function barWidth(percent: number | null): number {
	if (percent == null) return 0;
	return Math.max(0, Math.min(100, percent));
}

/**
 * Colour for a micronutrient relative to target (Cronometer-style: hitting the
 * target is good). green ≥ 100%, amber 50–99%, red < 50%, none when no target.
 */
export function microColor(percent: number | null): 'green' | 'amber' | 'red' | 'none' {
	if (percent == null) return 'none';
	if (percent >= 100) return 'green';
	if (percent >= 50) return 'amber';
	return 'red';
}

/**
 * Colour for an energy/macro ring: on-track near 100%, but going well over is a
 * warning. green 80–110%, amber 110–125% or 50–80%, red otherwise.
 */
export function macroColor(percent: number | null): 'green' | 'amber' | 'red' | 'none' {
	if (percent == null) return 'none';
	if (percent >= 80 && percent <= 110) return 'green';
	if ((percent > 110 && percent <= 125) || (percent >= 50 && percent < 80)) return 'amber';
	return 'red';
}

export function num(value: string | number | null | undefined): number {
	if (value == null) return 0;
	return typeof value === 'number' ? value : parseFloat(value) || 0;
}

/**
 * A distinct hue per macro (kept separate from the red/amber/green *status*
 * scale) so the macro bars read as four different things at a glance. Keyed by
 * nutrient slug; falls back to indigo for anything unmapped.
 */
export const MACRO_COLORS: Record<string, string> = {
	energy: 'bg-emerald-500',
	protein: 'bg-rose-500',
	carbohydrate: 'bg-amber-500',
	fat: 'bg-sky-500'
};

export function macroBarColor(slug: string | undefined): string {
	return (slug && MACRO_COLORS[slug]) || 'bg-indigo-600';
}
