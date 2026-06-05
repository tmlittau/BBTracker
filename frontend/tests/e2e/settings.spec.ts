import { expect, test } from '@playwright/test';

// Browser-level coverage of the profile/settings page against the live stack.

const PASSWORD = 'Sup3rStrongPass!';

async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('settings: edit and persist profile (sex, name)', async ({ page }) => {
	test.setTimeout(60_000);
	const email = `e2e+settings-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	await page.goto('/settings');
	await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
	// Email is shown but read-only.
	await expect(page.locator('#email')).toBeDisabled();

	// Edit sex + first name, then save.
	await page.locator('#sex').selectOption('male');
	await page.locator('#first_name').fill('Tim');
	await page.getByRole('button', { name: 'Save changes' }).click();
	await expect(page.getByText('Saved.')).toBeVisible({ timeout: 10_000 });

	// Reload → the change is persisted server-side.
	await page.reload();
	await expect(page.locator('#sex')).toHaveValue('male', { timeout: 10_000 });
	await expect(page.locator('#first_name')).toHaveValue('Tim');
});
