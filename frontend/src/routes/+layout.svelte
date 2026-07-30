<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { currentUser, fetchMe, logout } from '$lib/api/auth';

	let { children } = $props();

	// Session-cookie auth: "am I signed in?" == does /me/ succeed. `currentUser` is
	// undefined until checked, null when signed out, else the coach.
	const me = $derived($currentUser);
	const status = $derived(
		me === undefined ? 'loading' : me === null ? 'anon' : me.is_coach ? 'ready' : 'not_coach'
	);

	const nav = [
		{ href: '/', label: 'Roster' },
		{ href: '/check-ins', label: 'Check-ins' },
		{ href: '/templates', label: 'Templates' },
		{ href: '/settings', label: 'Settings' }
	];

	onMount(async () => {
		try {
			currentUser.set(await fetchMe());
		} catch {
			currentUser.set(null);
		}
	});

	// Keep unauthenticated users on the login page.
	$effect(() => {
		if (status === 'anon' && $page.url.pathname !== '/login') goto('/login');
	});

	async function signOut() {
		await logout();
		goto('/login');
	}
</script>

{#if status === 'loading'}
	<div class="grid min-h-screen place-items-center text-neutral-400">Loading…</div>
{:else if status === 'not_coach'}
	<div class="grid min-h-screen place-items-center px-6 text-center">
		<div>
			<h1 class="text-xl font-semibold">This account isn't a coach</h1>
			<p class="mt-2 text-sm text-neutral-400">
				The Coach Console requires a coach account. Signed in as {me?.email}.
			</p>
			<button class="mt-4 text-sm text-orange-400 hover:text-orange-300" onclick={signOut}>Sign out</button>
		</div>
	</div>
{:else if $page.url.pathname === '/login'}
	{@render children()}
{:else if status === 'ready'}
	<div class="flex h-screen">
		<aside class="flex w-56 shrink-0 flex-col border-r border-neutral-800 bg-neutral-900/40">
			<div class="px-4 py-4">
				<span class="text-lg font-bold text-gradient">TML Signal</span>
				<span class="block text-xs text-neutral-500">Coach Console</span>
			</div>
			<nav class="flex-1 px-2">
				{#each nav as item (item.href)}
					<a
						href={item.href}
						class="block rounded-md px-3 py-2 text-sm {$page.url.pathname === item.href
							? 'bg-neutral-800 text-white'
							: 'text-neutral-400 hover:bg-neutral-800/60 hover:text-white'}"
					>
						{item.label}
					</a>
				{/each}
			</nav>
			<div class="border-t border-neutral-800 p-3 text-xs text-neutral-500">
				<div class="truncate">{me?.email}</div>
				<button class="mt-1 text-orange-400 hover:text-orange-300" onclick={signOut}>Sign out</button>
			</div>
		</aside>
		<main class="flex-1 overflow-auto">
			{@render children()}
		</main>
	</div>
{/if}
