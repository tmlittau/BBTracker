import createClient from 'openapi-fetch';
import type { paths } from './schema';

// Typed client for the DRF data API. Relative baseUrl → dev proxy (browser) or
// same-origin reverse proxy (prod). Generated types come from `npm run gen:api`.
export const api = createClient<paths>({ baseUrl: '' });
