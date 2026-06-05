import { expect, test } from '@playwright/test';

// Browser-level coverage of the Nutrition module, mirroring scripts/verify_nutrition.py
// but driving the real SvelteKit UI against the dockerized stack (:5173 → :8000).
// Assumes `docker compose up -d` and seeded reference data (nutrients + foods).

const PASSWORD = 'Sup3rStrongPass!';

/**
 * SvelteKit hydrates a beat after the server-rendered HTML loads; an interaction
 * fired in that window is dropped. After a full page load, retry the first
 * interaction until its effect is observable. In-app navigation stays hydrated.
 */
async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('nutrition: set a target, log a food, see macros and micros', async ({ page }) => {
	test.setTimeout(90_000);
	const email = `e2e+${Date.now()}@example.com`;

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

	// --- Create + activate a target -------------------------------------------
	await page.goto('/nutrition/targets');
	await settle(
		async () => {
			await page.getByPlaceholder('Name (e.g. Cut, Maintenance)').fill('Cut');
			await page.locator('input[name="calories"]').fill('2000');
			await page.locator('input[name="protein_g"]').fill('180');
			await page.getByRole('button', { name: 'Create target' }).click();
		},
		// The new target appears in the list with a "Set active" button.
		() => expect(page.getByRole('button', { name: 'Set active' })).toBeVisible({ timeout: 2500 })
	);
	await page.getByRole('button', { name: 'Set active' }).click();
	// The green "Active" badge is a <span>; scope to it (the macro summary line
	// also contains the word) to keep this an unambiguous single match.
	await expect(page.locator('span.bg-green-900', { hasText: 'Active' })).toBeVisible({
		timeout: 10_000
	});

	// --- Diary: macro bars reflect the active target --------------------------
	await page.goto('/nutrition');
	await expect(page.getByRole('heading', { name: 'Nutrition' })).toBeVisible();
	// The macro summary shows the protein bar and the activated 2000 kcal target.
	// Scope to the section (toContainText ignores duplicate/hidden leaf nodes).
	await expect(page.getByTestId('macro-summary')).toContainText('Protein', { timeout: 10_000 });
	await expect(page.getByTestId('macro-summary')).toContainText('2000');

	// --- Meals are dynamic now: create "Breakfast", then log a food into it ----
	await page.getByRole('button', { name: 'Breakfast', exact: true }).click();
	const search = page.getByPlaceholder('Search foods to add…').first();
	await settle(
		() => search.fill('Chicken'),
		() => expect(page.getByRole('button', { name: /Chicken breast/ })).toBeVisible({ timeout: 1500 })
	);
	await page.getByRole('button', { name: /Chicken breast/ }).click();

	// Dialog: confirm the add (default serving + quantity 1).
	await expect(page.getByText('Adding to Breakfast')).toBeVisible();
	await page.getByRole('button', { name: 'Add', exact: true }).click();

	// Entry shows under the meal.
	await expect(page.getByText(/Chicken breast/).first()).toBeVisible({ timeout: 10_000 });

	// --- Toggle the top block to the micronutrient view -----------------------
	await page.getByRole('button', { name: 'Next view' }).click();
	await expect(page.getByRole('heading', { name: 'Micronutrients' })).toBeVisible();
	// Chicken contributes potassium; it should appear in the breakdown.
	await expect(page.getByText('Potassium')).toBeVisible();
});

test('nutrition: add a branded food by barcode from the library', async ({ page }) => {
	test.setTimeout(90_000);
	const email = `e2e+bc${Date.now()}@example.com`;

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

	// --- Food library: open the "Scan / add by barcode" panel ------------------
	await page.goto('/nutrition/foods');
	await expect(page.getByRole('heading', { name: 'Food library' })).toBeVisible();
	const barcodeInput = page.locator('input[name="barcode"]');
	await settle(
		() => page.getByRole('button', { name: 'Scan / add by barcode' }).click(),
		() => expect(barcodeInput).toBeVisible({ timeout: 1500 })
	);

	// --- Import a real branded product from Open Food Facts --------------------
	// Nutella (3017620422003). The import is idempotent (returns the existing
	// global food on repeat runs). Requires OFF reachable — the same live path
	// asserted headlessly by scripts/verify_nutrition.py.
	await barcodeInput.fill('3017620422003');
	await page.getByRole('button', { name: 'Look up' }).click();
	// Either the green confirmation or the imported food landing in the list.
	const added = page.getByText(/^Added /);
	const inList = page.getByText('Nutella').first();
	await expect(added.or(inList)).toBeVisible({ timeout: 25_000 });
});
