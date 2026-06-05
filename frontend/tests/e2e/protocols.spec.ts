import { expect, test } from '@playwright/test';

// Browser-level coverage of the Protocols module, mirroring scripts/verify_protocols.py
// but driving the real SvelteKit UI against the dockerized stack (:5173 → :8000).
// Assumes `docker compose up -d` and `seed_protocols` (compounds, sites, markers).

const PASSWORD = 'Sup3rStrongPass!';

async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('protocols: log an injection with the body-map, see it under today', async ({ page }) => {
	test.setTimeout(90_000);
	// Random suffix (not just Date.now()) so parallel specs never collide on email.
	const email = `e2e+proto-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

	// --- Register --------------------------------------------------------------
	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	// --- Protocols landing carries the disclaimer -----------------------------
	await page.goto('/protocols');
	await expect(page.getByRole('heading', { name: 'Protocols' })).toBeVisible();
	await expect(page.getByText(/not medical advice/i)).toBeVisible();

	// --- Dose logger: pick a seeded injectable compound -----------------------
	await page.goto('/protocols/log');
	await settle(
		() => page.getByRole('heading', { name: 'Log a dose' }).waitFor(),
		() => expect(page.getByRole('button', { name: 'Medication / PED' })).toBeVisible({ timeout: 1500 })
	);
	// Default route is IM, so the body map should be visible; choose a compound.
	await page.locator('select').first().selectOption({ label: 'Testosterone Enanthate' });
	await page.locator('input[name="amount"]').fill('125');

	// The interactive body-map picker exposes sites as buttons; pick one.
	const suggested = page.getByRole('button', { name: /Use suggested:/ });
	if (await suggested.isVisible().catch(() => false)) {
		await suggested.click();
	} else {
		await page.getByRole('button', { name: /glute|quad|delt|ventroglute/i }).first().click();
	}

	await page.getByRole('button', { name: 'Log dose', exact: true }).click();

	// The dose appears under "Today's doses". (Scope to that section — the compound
	// name also exists as a hidden <option> in the picker, so a bare getByText would
	// match the wrong, invisible element.)
	const todaySection = page.locator('section', { hasText: "Today's doses" });
	await expect(todaySection.getByRole('heading', { name: "Today's doses" })).toBeVisible();
	await expect(todaySection.getByText('Nothing logged today yet.')).toHaveCount(0, {
		timeout: 10_000
	});
	await expect(todaySection.getByText(/Testosterone Enanthate/)).toBeVisible({ timeout: 10_000 });

	// --- Compound library shows a concentration curve -------------------------
	await page.goto('/protocols/compounds');
	await expect(page.getByRole('heading', { name: 'Compound library' })).toBeVisible();
	await page.getByRole('button', { name: 'Curve' }).first().click();
	await expect(page.getByText(/active amount \(30 days\)/i)).toBeVisible({ timeout: 10_000 });

	// --- Bloodwork: log a result and see it in the trend ----------------------
	await page.goto('/protocols/bloodwork');
	await expect(page.getByRole('heading', { name: /Bloodwork/ })).toBeVisible();
	// BP is the simplest unambiguous write on this page.
	await page.locator('input[name="systolic"]').fill('122');
	await page.locator('input[name="diastolic"]').fill('78');
	await page.getByRole('button', { name: 'Log BP' }).click();
	await expect(page.getByText('122/78')).toBeVisible({ timeout: 10_000 });
});
