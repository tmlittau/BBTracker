import { expect, test } from '@playwright/test';

// Phone-viewport coverage (Pixel 5) of the mobile shell + the touch-first logger.
// Runs only under the `mobile` Playwright project against the live stack.

const PASSWORD = 'Sup3rStrongPass!';
const EXERCISE = 'Barbell Bench Press'; // seeded

async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('mobile: bottom-nav shell + touch-first set logging', async ({ page }) => {
	test.setTimeout(90_000);
	const email = `e2e+mob-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

	// --- Register ---
	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	// --- Mobile shell: bottom tab bar present, desktop nav's account menu button shows ---
	const bottomNav = page.getByRole('navigation', { name: 'Primary' });
	await expect(bottomNav).toBeVisible();
	await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();

	// Tap a tab to navigate (client-side).
	await bottomNav.getByRole('link', { name: 'Training' }).click();
	await expect(page).toHaveURL(/\/training$/, { timeout: 10_000 });
	await expect(page.getByRole('heading', { name: 'Training' })).toBeVisible();

	// --- Touch-first logger ---
	await page.goto('/training/log');
	await settle(
		() => page.getByRole('button', { name: 'Start empty workout' }).click(),
		() => expect(page.getByRole('button', { name: 'Finish workout' })).toBeVisible({ timeout: 2500 })
	);
	await page.locator('select').last().selectOption({ label: EXERCISE });
	await expect(page.getByRole('heading', { name: EXERCISE })).toBeVisible({ timeout: 10_000 });

	// The weight stepper bumps by 2.5 (one-handed entry).
	await page.getByRole('button', { name: 'increase' }).first().click();
	await expect(page.getByLabel('Weight')).toHaveValue('2.5');

	// Log a set: fill via the labelled stepper inputs, then Log set.
	await page.getByLabel('Weight').fill('100');
	await page.getByLabel('Reps').fill('5');
	await page.getByRole('button', { name: 'Log set' }).click();

	// The set row turns green (completed) and the rest countdown appears.
	await expect(page.getByTestId('set-completed')).toBeVisible({ timeout: 10_000 });
	await expect(page.getByTestId('set-completed')).toContainText('100');
	await expect(page.getByTestId('rest-timer')).toBeVisible();

	// Finish (all sets complete → no prompt).
	await page.getByRole('button', { name: 'Finish workout' }).click();
	await expect(page.getByText('Workout finished')).toBeVisible({ timeout: 10_000 });
});
