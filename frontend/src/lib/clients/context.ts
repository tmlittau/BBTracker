// Shared context set by the client workspace layout, read by the tab pages/builders.
// Uses getters so `brief`/`canEdit` stay reactive after the async roster fetch resolves.
import type { ClientBrief } from '../coaching/api';

export const CLIENT_CTX = Symbol('client');

export interface ClientContext {
	readonly brief: ClientBrief | null;
	readonly canEdit: boolean;
}
