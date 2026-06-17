// Extract a human-readable message from an error thrown by the typed API
// wrappers. Their `Error.message` looks like "DELETE /foods/5/ → 400 <body>",
// where <body> is the DRF JSON — a {detail}, a field-errors object, a bare
// ["string"] (non-field ValidationError), or a quoted string.
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong.'): string {
	const msg = (err as Error)?.message ?? String(err);
	const i = msg.search(/[[{]/);
	if (i >= 0) {
		try {
			const body = JSON.parse(msg.slice(i));
			if (typeof body === 'string') return body;
			if (Array.isArray(body)) {
				const strs = body.filter((x) => typeof x === 'string');
				if (strs.length) return strs.join(' ');
			} else if (body && typeof body === 'object') {
				if (body.detail) {
					return Array.isArray(body.detail) ? body.detail.join(' ') : String(body.detail);
				}
				const vals = Object.values(body)
					.flat()
					.filter((x) => typeof x === 'string');
				if (vals.length) return vals.join(' ');
			}
		} catch {
			/* not JSON — fall through to the raw message */
		}
	}
	return msg || fallback;
}
