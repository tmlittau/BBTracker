import { defineConfig } from '@playwright/test';

// Assumes the full stack is already running (docker compose up).
export default defineConfig({
	testDir: 'tests/e2e',
	timeout: 30_000,
	use: { baseURL: 'http://localhost:5173' }
});
