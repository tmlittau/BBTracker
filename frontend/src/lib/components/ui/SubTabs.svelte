<script lang="ts">
	import { page } from '$app/stores';

	type Tab = { href: string; label: string; match?: (p: string) => boolean };

	// `activeClass` is passed as a literal per domain so Tailwind keeps the classes.
	let { tabs, activeClass }: { tabs: Tab[]; activeClass: string } = $props();

	function isActive(t: Tab): boolean {
		const p = $page.url.pathname;
		return t.match ? t.match(p) : p === t.href || p.startsWith(t.href + '/');
	}
</script>

<nav class="mb-5 flex gap-1 overflow-x-auto border-b border-neutral-800 text-sm">
	{#each tabs as t (t.href)}
		<a
			href={t.href}
			class="whitespace-nowrap border-b-2 px-3 py-2 transition-colors {isActive(t)
				? activeClass
				: 'border-transparent text-neutral-400 hover:text-neutral-200'}"
		>
			{t.label}
		</a>
	{/each}
</nav>
