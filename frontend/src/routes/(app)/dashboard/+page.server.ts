import type { PageServerLoad } from './$types';
import { backendFetch } from '$lib/server/backend';

export const load: PageServerLoad = async ({ request, locals }) => {
	const cookie = request.headers.get('cookie');
	// `me` is the user the hook already resolved (locals.user) — no extra /auth/me
	// round-trip. The dashboard only needs the email for the header.
	const todayRes = await backendFetch('/api/v1/dashboard/today/', { cookie });
	return {
		me: locals.user,
		today: todayRes.ok ? await todayRes.json() : null
	};
};
