<script lang="ts">
	import { page } from '$app/stores';

	type Icon = 'home' | 'dumbbell' | 'food' | 'vial' | 'camera';
	type Tab = { href: string; label: string; accent: string; icon: Icon; match?: (p: string) => boolean };

	// The five primary sections, thumb-reachable. Active tab uses the per-domain
	// accent. Phases / Settings / Log out live in the header account menu.
	const tabs: Tab[] = [
		{ href: '/dashboard', label: 'Today', accent: 'text-white', icon: 'home' },
		{ href: '/training', label: 'Training', accent: 'text-indigo-400', icon: 'dumbbell' },
		{ href: '/nutrition', label: 'Nutrition', accent: 'text-emerald-400', icon: 'food' },
		{ href: '/protocols', label: 'Protocols', accent: 'text-violet-400', icon: 'vial' },
		{ href: '/diary', label: 'Diary', accent: 'text-sky-400', icon: 'camera' }
	];

	function isActive(t: Tab): boolean {
		const p = $page.url.pathname;
		return t.match ? t.match(p) : p === t.href || p.startsWith(t.href + '/');
	}
</script>

<nav
	class="pb-safe fixed inset-x-0 bottom-0 z-30 flex border-t border-neutral-800 bg-neutral-950/95 backdrop-blur md:hidden"
	aria-label="Primary"
>
	{#each tabs as t (t.href)}
		<a
			href={t.href}
			aria-current={isActive(t) ? 'page' : undefined}
			class="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] {isActive(t)
				? t.accent
				: 'text-neutral-500'}"
		>
			<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				{#if t.icon === 'home'}
					<path d="M3 11.5 12 4l9 7.5" /><path d="M5 10v10h14V10" />
				{:else if t.icon === 'dumbbell'}
					<path d="M6.5 6.5v11M3.5 9v6M17.5 6.5v11M20.5 9v6M6.5 12h11" />
				{:else if t.icon === 'food'}
					<path d="M5 3v8a2 2 0 0 0 4 0V3M7 11v10M16.5 3c-1.6 0-2.5 2-2.5 5s1 4 2.5 4 2.5-1 2.5-4-.9-5-2.5-5zM16.5 16v5" />
				{:else if t.icon === 'vial'}
					<path d="M9 3h6M10 3v10a3 3 0 0 0 6 0V3M9.5 13h7" />
				{:else if t.icon === 'camera'}
					<path d="M3 8a2 2 0 0 1 2-2h2l1.4-2h7.2L19 6h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><circle cx="12" cy="12.5" r="3.2" />
				{/if}
			</svg>
			<span>{t.label}</span>
		</a>
	{/each}
</nav>
