<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { logout } from '$lib/api/auth';
	import { getMe } from '$lib/api/profile';
	import BottomNav from '$lib/components/ui/BottomNav.svelte';

	let { children, data } = $props();
	let menuOpen = $state(false);
	let isCoach = $state(false);

	// The "Coaching" entry only exists for coach accounts (User.is_coach).
	onMount(async () => {
		isCoach = (await getMe().catch(() => null))?.is_coach ?? false;
	});

	const BASE_LINKS = [
		{ href: '/dashboard', label: 'Today', accent: 'text-white' },
		{ href: '/training', label: 'Training', accent: 'text-indigo-300' },
		{ href: '/nutrition', label: 'Nutrition', accent: 'text-emerald-300' },
		{ href: '/protocols', label: 'Protocols', accent: 'text-violet-300' },
		{ href: '/diary', label: 'Diary', accent: 'text-sky-300' },
		{ href: '/analysis', label: 'Analysis', accent: 'text-rose-300' },
		{ href: '/phases', label: 'Phases', accent: 'text-amber-300' }
	];
	const links = $derived(
		isCoach
			? [...BASE_LINKS, { href: '/coach', label: 'Coaching', accent: 'text-teal-300' }]
			: BASE_LINKS
	);

	async function onLogout() {
		await logout();
		await goto('/login');
	}

	function isActive(href: string): boolean {
		return $page.url.pathname === href || $page.url.pathname.startsWith(href + '/');
	}
</script>

<div class="min-h-screen">
	<header class="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
		<!-- Desktop nav -->
		<nav class="hidden items-center gap-5 md:flex">
			<a href="/dashboard" class="flex items-center gap-2 font-bold">
				<span class="flex h-7 w-7 items-center justify-center rounded-lg bg-brand">
					<svg class="h-4 w-4 text-white" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<rect x="4" y="11" width="3.5" height="9" rx="1" /><rect x="10.25" y="6" width="3.5" height="14" rx="1" /><rect x="16.5" y="8.5" width="3.5" height="11.5" rx="1" />
					</svg>
				</span>
				<span class="text-gradient">BBTracker</span>
			</a>
			{#each links as link (link.href)}
				<a
					href={link.href}
					class="text-sm font-medium {isActive(link.href)
						? link.accent
						: 'text-neutral-400 hover:text-neutral-200'}"
				>
					{link.label}
				</a>
			{/each}
		</nav>
		<!-- Mobile brand -->
		<a href="/dashboard" class="flex items-center gap-2 font-bold md:hidden">
			<span class="flex h-7 w-7 items-center justify-center rounded-lg bg-brand">
				<svg class="h-4 w-4 text-white" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
					<rect x="4" y="11" width="3.5" height="9" rx="1" /><rect x="10.25" y="6" width="3.5" height="14" rx="1" /><rect x="16.5" y="8.5" width="3.5" height="11.5" rx="1" />
				</svg>
			</span>
			<span class="text-gradient">BBTracker</span>
		</a>

		<div class="flex items-center gap-3 text-sm">
			<a
				href="/settings"
				class="hidden hover:text-white sm:inline {isActive('/settings')
					? 'text-white'
					: 'text-neutral-400'}"
			>
				{data.user?.email}
			</a>
			<button class="hidden text-neutral-300 hover:text-white md:inline" onclick={onLogout}>Log out</button>
			<!-- Mobile account menu -->
			<button
				class="text-neutral-300 hover:text-white md:hidden"
				aria-label="Account menu"
				aria-expanded={menuOpen}
				onclick={() => (menuOpen = !menuOpen)}
			>
				<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="8" r="3.2" /><path d="M5 20c0-3.3 3.1-5.5 7-5.5s7 2.2 7 5.5" />
				</svg>
			</button>
		</div>
	</header>

	<!-- Mobile account sheet -->
	{#if menuOpen}
		<button class="fixed inset-0 z-30 bg-black/40 md:hidden" aria-label="Close menu" onclick={() => (menuOpen = false)}></button>
		<div class="fixed right-3 top-14 z-40 w-56 rounded-lg border border-neutral-700 bg-neutral-950 p-2 text-sm shadow-xl md:hidden">
			<p class="truncate px-3 py-2 text-xs text-neutral-500">{data.user?.email}</p>
			<a href="/phases" class="block rounded px-3 py-2 hover:bg-neutral-800" onclick={() => (menuOpen = false)}>Phases</a>
			{#if isCoach}
				<a href="/coach" class="block rounded px-3 py-2 hover:bg-neutral-800" onclick={() => (menuOpen = false)}>Coaching</a>
			{/if}
			<a href="/settings" class="block rounded px-3 py-2 hover:bg-neutral-800" onclick={() => (menuOpen = false)}>Settings</a>
			<button class="block w-full rounded px-3 py-2 text-left text-red-400 hover:bg-neutral-800" onclick={onLogout}>Log out</button>
		</div>
	{/if}

	<main class="mx-auto max-w-4xl px-4 pt-6 pb-24 md:pb-10">
		{@render children()}
	</main>

	<BottomNav />
</div>
