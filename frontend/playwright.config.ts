import { defineConfig, devices } from '@playwright/test';

// Assumes the full stack is already running (docker compose up).
// Two projects: the existing specs run at desktop size; mobile.spec.ts runs on a
// phone viewport (Pixel 5: 393px, touch) to cover the responsive shell + logger.
export default defineConfig({
	testDir: 'tests/e2e',
	timeout: 30_000,
	use: { baseURL: 'http://localhost:5173' },
	projects: [
		{
			name: 'desktop',
			use: { ...devices['Desktop Chrome'] },
			testIgnore: '**/mobile.spec.ts'
		},
		{
			name: 'mobile',
			use: { ...devices['Pixel 5'] },
			testMatch: '**/mobile.spec.ts'
		}
	]
});
