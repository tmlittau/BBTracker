<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { logout } from '$lib/api/auth';
	import BottomNav from '$lib/components/ui/BottomNav.svelte';

	let { children, data } = $props();
	let menuOpen = $state(false);

	const links = [
		{ href: '/dashboard', label: 'Today', accent: 'text-white' },
		{ href: '/training', label: 'Training', accent: 'text-indigo-300' },
		{ href: '/nutrition', label: 'Nutrition', accent: 'text-emerald-300' },
		{ href: '/protocols', label: 'Protocols', accent: 'text-violet-300' },
		{ href: '/diary', label: 'Diary', accent: 'text-sky-300' },
		{ href: '/body', label: 'Body', accent: 'text-rose-300' },
		{ href: '/phases', label: 'Phases', accent: 'text-amber-300' }
	];

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
			<a href="/dashboard" class="font-bold text-indigo-400">BBTracker</a>
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
		<a href="/dashboard" class="font-bold text-indigo-400 md:hidden">BBTracker</a>

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
			<a href="/settings" class="block rounded px-3 py-2 hover:bg-neutral-800" onclick={() => (menuOpen = false)}>Settings</a>
			<button class="block w-full rounded px-3 py-2 text-left text-red-400 hover:bg-neutral-800" onclick={onLogout}>Log out</button>
		</div>
	{/if}

	<main class="mx-auto max-w-4xl px-4 pt-6 pb-24 md:pb-10">
		{@render children()}
	</main>

	<BottomNav />
</div>
