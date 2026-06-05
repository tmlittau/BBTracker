<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { logout } from '$lib/api/auth';

	let { children, data } = $props();

	const links = [
		{ href: '/dashboard', label: 'Today', accent: 'text-white' },
		{ href: '/training', label: 'Training', accent: 'text-indigo-300' },
		{ href: '/nutrition', label: 'Nutrition', accent: 'text-emerald-300' },
		{ href: '/protocols', label: 'Protocols', accent: 'text-violet-300' },
		{ href: '/diary', label: 'Diary', accent: 'text-sky-300' },
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
		<nav class="flex items-center gap-5">
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
		<div class="flex items-center gap-3 text-sm">
			<a
				href="/settings"
				class="hidden hover:text-white sm:inline {isActive('/settings')
					? 'text-white'
					: 'text-neutral-400'}"
			>
				{data.user?.email}
			</a>
			<button class="text-neutral-300 hover:text-white" onclick={onLogout}>Log out</button>
		</div>
	</header>
	<main class="mx-auto max-w-4xl px-4 py-6">
		{@render children()}
	</main>
</div>
