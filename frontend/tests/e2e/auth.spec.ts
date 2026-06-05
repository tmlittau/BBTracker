import { expect, test } from '@playwright/test';

test('protected route redirects to login when anonymous', async ({ page }) => {
	await page.goto('/dashboard');
	await expect(page).toHaveURL(/\/login/);
});

test('a new user can register and reach the dashboard', async ({ page }) => {
	const email = `e2e+${Date.now()}@example.com`;

	await page.goto('/login');
	// SvelteKit hydrates a beat after the HTML loads; a click fired in that window
	// is dropped. Retry the toggle until the signup form ("Create account") shows.
	await expect(async () => {
		await page.getByText('Need an account? Sign up').click();
		await expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({
			timeout: 1500
		});
	}).toPass({ timeout: 20_000 });
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill('Sup3rStrongPass!');
	await page.getByRole('button', { name: 'Create account' }).click();

	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
	// The email renders both in the nav and the body, so scope to the "Signed in
	// as …" line to keep this a single, unambiguous match.
	await expect(page.getByText(`Signed in as ${email}`)).toBeVisible();
});
