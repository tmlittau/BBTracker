import { expect, test } from '@playwright/test';

// Browser-level coverage of the Training MVP, mirroring scripts/verify_training.py
// but driving the real SvelteKit UI against the dockerized stack (:5173 → :8000).
// Assumes `docker compose up -d` and seeded reference data (muscles + exercises).

const PASSWORD = 'Sup3rStrongPass!';
const EXERCISE = 'Barbell Bench Press'; // seeded; primary muscle = Chest

/**
 * SvelteKit hydrates a beat after the server-rendered HTML loads; a click or
 * submit fired in that window is silently dropped (the handler isn't attached
 * yet). After a full page load, retry the first interaction until its effect is
 * observable. Subsequent in-app navigation is client-side, so it stays hydrated.
 */
async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('training: build a program, log a workout, see PRs and per-muscle volume', async ({
	page
}) => {
	test.setTimeout(90_000); // a long, sequential, network-bound flow
	const email = `e2e+${Date.now()}@example.com`;

	// --- Register a fresh user -------------------------------------------------
	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	// --- Training landing ------------------------------------------------------
	await page.goto('/training');
	await expect(page.getByRole('heading', { name: 'Training' })).toBeVisible();

	// --- Create a program (the form navigates to the new program's detail page) -
	await page.goto('/training/programs');
	await settle(
		async () => {
			await page.getByPlaceholder('New program name (e.g. Push/Pull/Legs)').fill('Push/Pull/Legs');
			await page.getByRole('button', { name: 'Create' }).click();
		},
		() => expect(page).toHaveURL(/\/training\/programs\/\d+/, { timeout: 2500 })
	);
	await expect(page.getByRole('heading', { name: 'Push/Pull/Legs', exact: true })).toBeVisible();

	// --- Add a training day (page reached via client-side nav → already hydrated) -
	await page.getByPlaceholder('Add a training day (e.g. Push)').fill('Push');
	await page.getByRole('button', { name: 'Add day' }).click();
	// `exact` so the day's "Push" heading doesn't also match "Push/Pull/Legs".
	await expect(page.getByRole('heading', { name: 'Push', exact: true })).toBeVisible();

	// --- Add an exercise slot (creates the slot + 3 default working sets) -------
	// The day card holds the only <select> on this page.
	await page.locator('select').last().selectOption({ label: EXERCISE });
	// The slot renders an editable set table (3 default working sets) + an Add-set control.
	await expect(page.getByRole('button', { name: '+ Add set' }).first()).toBeVisible({ timeout: 15_000 });

	// --- Start a workout from the logger --------------------------------------
	await page.goto('/training/log');
	await settle(
		() => page.getByRole('button', { name: 'Start empty workout' }).click(),
		() => expect(page.getByRole('button', { name: 'Finish workout' })).toBeVisible({ timeout: 2500 })
	);
	// The add-exercise picker is always the last <select> in the DOM.
	await page.locator('select').last().selectOption({ label: EXERCISE });
	await expect(page.getByRole('heading', { name: EXERCISE })).toBeVisible({ timeout: 10_000 });

	// --- Log the first set: the live estimated-1RM hint shows while entering ----
	await page.getByLabel('Weight').fill('100');
	await page.getByLabel('Reps').fill('5');
	await expect(page.getByText('Estimated 1RM for this set')).toBeVisible();
	await page.getByRole('button', { name: 'Log set' }).click();

	// The first working set is always a PR, and its weight lands in the set table.
	await expect(page.getByText('PR', { exact: true }).first()).toBeVisible({ timeout: 10_000 });
	await expect(page.getByText('100.00')).toBeVisible();

	// --- Log a heavier second set ---------------------------------------------
	// (logSet() clears reps but keeps weight, so re-enter both.)
	await page.getByLabel('Weight').fill('110');
	await page.getByLabel('Reps').fill('5');
	await page.getByRole('button', { name: 'Log set' }).click();
	await expect(page.getByText('110.00')).toBeVisible({ timeout: 10_000 });

	// --- Finish the workout ----------------------------------------------------
	await page.getByRole('button', { name: 'Finish workout' }).click();
	await expect(page.getByText('Workout finished')).toBeVisible({ timeout: 10_000 });

	// --- History: the workout and per-muscle volume should render -------------
	await page.goto('/training/history');
	await expect(page.getByRole('heading', { name: 'All workouts' })).toBeVisible();
	await expect(page.getByText('No workouts logged yet.')).toHaveCount(0);
	await expect(page.getByText('Workout', { exact: true })).toBeVisible({ timeout: 10_000 });

	// Volume credits the exercise's primary muscle (Chest) for both working sets.
	await expect(page.getByRole('heading', { name: /Weekly volume by muscle/ })).toBeVisible();
	await expect(page.getByText('No working sets logged in this window.')).toHaveCount(0);
	await expect(page.getByText('Chest', { exact: true })).toBeVisible({ timeout: 10_000 });
	await expect(page.getByText('2 sets').first()).toBeVisible();
});
