// App-wide time-of-day slot labels. The keys are fixed (waking/am/noon/pm/night);
// the display names are user-customisable in reminder settings. Loaded once and
// cached so any view can show the user's chosen names without refetching.
import { derived, writable } from 'svelte/store';

import { notificationsApi, type ReminderSettings } from './api';

export const SLOT_KEYS = ['waking', 'am', 'noon', 'pm', 'night'] as const;
export type SlotKey = (typeof SLOT_KEYS)[number];
export const SLOT_DEFAULTS: Record<string, string> = {
	waking: 'Waking',
	am: 'AM',
	noon: 'Noon',
	pm: 'PM',
	night: 'Night'
};

/** Custom names over the defaults, from a reminder-settings payload. */
export function mergeSlotLabels(r: ReminderSettings | null): Record<string, string> {
	const out = { ...SLOT_DEFAULTS };
	if (r) {
		for (const k of SLOT_KEYS) {
			const v = (r as unknown as Record<string, unknown>)[`${k}_label`];
			if (typeof v === 'string' && v.trim()) out[k] = v.trim();
		}
	}
	return out;
}

const _labels = writable<Record<string, string>>({ ...SLOT_DEFAULTS });
let loaded = false;

/** Load slot labels once (no-op after the first successful load). */
export async function ensureSlotLabels(): Promise<void> {
	if (loaded) return;
	try {
		_labels.set(mergeSlotLabels(await notificationsApi.settings()));
		loaded = true;
	} catch {
		// keep defaults; allow a later retry
	}
}

/** Push fresh labels (e.g. right after the settings page saves). */
export function setSlotLabels(r: ReminderSettings | null): void {
	_labels.set(mergeSlotLabels(r));
	loaded = true;
}

/** Reactive map of slot key → display label. */
export const slotLabels = { subscribe: _labels.subscribe };

/** Reactive [{ key, label }] in canonical order — drop-in for the old TIMES_OF_DAY. */
export const timesOfDay = derived(_labels, ($l) =>
	SLOT_KEYS.map((k) => ({ key: k as string, label: $l[k] }))
);
