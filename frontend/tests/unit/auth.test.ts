import { describe, expect, it } from 'vitest';
import { firstError, isPending2fa } from '../../src/lib/api/auth';

describe('auth helpers', () => {
	it('extracts the first allauth error message', () => {
		expect(firstError({ errors: [{ message: 'Email exists' }] })).toBe('Email exists');
		expect(firstError({})).toBe('Request failed');
		expect(firstError(null)).toBe('Request failed');
	});

	it('detects a pending MFA flow', () => {
		expect(isPending2fa({ data: { flows: [{ id: 'mfa_authenticate', is_pending: true }] } })).toBe(
			true
		);
		expect(isPending2fa({ data: { flows: [{ id: 'login', is_pending: true }] } })).toBe(false);
		expect(isPending2fa({})).toBe(false);
	});
});
