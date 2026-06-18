import { writable } from 'svelte/store';

// Bumped when a measurement is added (from the Analysis layout's modal) so the
// Body sub-view reloads its data even though the modal lives in the layout.
export const measurementsVersion = writable(0);
