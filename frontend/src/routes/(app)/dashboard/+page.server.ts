import type { PageServerLoad } from './$types';
import { backendFetch } from '$lib/server/backend';

export const load: PageServerLoad = async ({ request }) => {
	const cookie = request.headers.get('cookie');
	const [meRes, todayRes] = await Promise.all([
		backendFetch('/api/v1/auth/me/', { cookie }),
		backendFetch('/api/v1/dashboard/today/', { cookie })
	]);
	return {
		me: meRes.ok ? await meRes.json() : null,
		today: todayRes.ok ? await todayRes.json() : null
	};
};
