import type { Handle } from '@sveltejs/kit';
import { getSession } from '$lib/server/backend';

export const handle: Handle = async ({ event, resolve }) => {
	const cookie = event.request.headers.get('cookie');
	event.locals.user = await getSession(cookie);
	return resolve(event);
};
