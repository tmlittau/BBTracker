// See https://svelte.dev/docs/kit/types#app.d.ts

export interface AuthUser {
	id: number;
	email: string;
	display?: string;
}

declare global {
	namespace App {
		interface Locals {
			user: AuthUser | null;
		}
		interface PageData {
			user?: AuthUser | null;
		}
	}
}

export {};
