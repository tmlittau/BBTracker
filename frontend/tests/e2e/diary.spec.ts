import { expect, test } from '@playwright/test';

// Browser-level coverage of the Progress Diary against the live stack
// (:5173 → :8000). Assumes `docker compose up -d` + `seed_diary`.

const PASSWORD = 'Sup3rStrongPass!';
// A real 64×48 PNG (DRF's ImageField validates via Pillow and rejects degenerate
// 1×1 stubs); the backend re-encodes to JPEG + makes a thumbnail.
const PNG_64x48 = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAAEAAAAAwCAIAAAAuKetIAAAAUklEQVR4nO3PMQ0AIADAMEAIwvAvBBEcDcmqYJtn7/GzpQNeNaA1oDWgNaA1oDWgNaA1oDWgNaA1oDWgNaA1oDWgNaA1oDWgNaA1oDWgNaA1oF0iBAD2KawQwgAAAABJRU5ErkJggg==',
	'base64'
);

async function settle(interact: () => Promise<void>, confirm: () => Promise<unknown>) {
	await expect(async () => {
		await interact();
		await confirm();
	}).toPass({ timeout: 20_000, intervals: [100, 250, 500, 1000] });
}

test('diary: add a check-in and upload a progress photo', async ({ page }) => {
	test.setTimeout(90_000);
	const email = `e2e+diary-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

	await page.goto('/login');
	await settle(
		() => page.getByRole('button', { name: 'Need an account? Sign up' }).click(),
		() => expect(page.getByRole('button', { name: 'Create account' })).toBeVisible({ timeout: 1500 })
	);
	await page.getByPlaceholder('Email').fill(email);
	await page.getByPlaceholder('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Create account' }).click();
	await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

	// --- Check-in ---
	await page.goto('/diary/check-in');
	await settle(
		async () => {
			await page.locator('#bw').fill('84.5');
			await page.getByRole('button', { name: 'Energy 4 of 5' }).click();
			await page.locator('textarea[name="notes"]').fill('felt strong');
			await page.getByRole('button', { name: 'Save check-in' }).click();
		},
		() => expect(page.getByText('Saved.')).toBeVisible({ timeout: 2500 })
	);

	// It shows on the diary home.
	await page.goto('/diary');
	await expect(page.getByRole('heading', { name: 'Progress diary' })).toBeVisible();
	await expect(page.getByText(/felt strong/)).toBeVisible({ timeout: 10_000 });

	// --- Photo upload ---
	await page.goto('/diary/photos');
	await expect(page.getByRole('heading', { name: 'Progress photos' })).toBeVisible();
	await page.locator('#photo-file').setInputFiles({
		name: 'pose.png',
		mimeType: 'image/png',
		buffer: PNG_64x48
	});
	await page.getByRole('button', { name: 'Upload photo' }).click();

	// The uploaded photo appears in the gallery and its thumbnail actually streams
	// (naturalWidth > 0 once the browser decodes the bytes the API served).
	const gallery = page.locator('section', { hasText: 'Gallery' });
	await expect(gallery.locator('img').first()).toBeVisible({ timeout: 15_000 });
	await expect
		.poll(
			() => gallery.locator('img').first().evaluate((el: HTMLImageElement) => el.naturalWidth),
			{ timeout: 15_000 }
		)
		.toBeGreaterThan(0);
});
