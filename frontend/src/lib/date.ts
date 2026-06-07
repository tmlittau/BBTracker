// Local calendar-date helpers. Using `toISOString().slice(0,10)` returns the
// *UTC* date, which is off by one for users east/west of UTC (e.g. "today" is
// wrong just after midnight, and date arithmetic drifts). These compute from the
// browser's local timezone instead.

/** Local date as YYYY-MM-DD (not UTC). */
export function isoDate(d: Date = new Date()): string {
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${y}-${m}-${day}`;
}

/** Shift a YYYY-MM-DD string by N days, staying in local time. */
export function shiftISODate(date: string, days: number): string {
	const d = new Date(date + 'T00:00:00'); // parsed as local midnight
	d.setDate(d.getDate() + days);
	return isoDate(d);
}
