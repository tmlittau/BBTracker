import { expect, test } from '@playwright/test';

// Browser-level coverage of the self-coaching layer (phases timeline, real
// dashboard, weekly check-in) against the live stack. Assumes `docker compose
// up -d` + seeded reference data.

const PASSWORD = 'Sup3rStrongPass!';

async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('coaching: create a phase and see it on the dashboard + weekly check-in', async ({ page }) => {
	test.setTimeout(90_000);
	const email = `e2e+coach-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	// Dashboard with no phase yet prompts to start one.
	await expect(page.getByText('No active phase.')).toBeVisible({ timeout: 10_000 });

	// Create an ongoing phase that covers today.
	await page.goto('/phases');
	await settle(
		async () => {
			await page.getByPlaceholder('Name (e.g. Summer prep)').fill('Off-season bulk');
			await page.locator('input[name="start_date"]').fill('2026-01-01');
			await page.getByRole('button', { name: 'Create phase' }).click();
		},
		() => expect(page.locator('span.bg-green-900', { hasText: 'Ongoing' })).toBeVisible({ timeout: 2500 })
	);

	// It now surfaces as the current phase on the dashboard.
	await page.goto('/dashboard');
	await expect(page.getByText('Current phase')).toBeVisible({ timeout: 10_000 });
	await expect(page.getByText('Off-season bulk').first()).toBeVisible();

	// Weekly check-in renders and resolves the phase.
	await page.goto('/check-in');
	await expect(page.getByRole('heading', { name: 'Weekly check-in' })).toBeVisible();
	await expect(page.getByText(/phase: Off-season bulk/)).toBeVisible({ timeout: 10_000 });
	await expect(page.getByRole('heading', { name: 'Training' })).toBeVisible();
});
