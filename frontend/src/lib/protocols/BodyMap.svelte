<script lang="ts">
	import { siteStatus, SITE_COLORS, type SiteStatus } from './calc';
	import type { SiteRecency } from './api';

	let {
		sites,
		selected = $bindable(null),
		onpick
	}: {
		sites: SiteRecency[];
		selected?: number | null;
		onpick?: (site: SiteRecency) => void;
	} = $props();

	function statusOf(site: SiteRecency): SiteStatus {
		return (site.status as SiteStatus) ?? siteStatus(site.days_since);
	}

	function colorFor(site: SiteRecency): string {
		return SITE_COLORS[statusOf(site)] ?? '#737373';
	}

	function pick(site: SiteRecency) {
		selected = site.id;
		onpick?.(site);
	}
</script>

<div class="flex flex-col items-center">
	<!-- Visual recency map (decorative — selection happens via the buttons below). -->
	<svg viewBox="0 0 100 120" class="h-72 w-auto" aria-hidden="true">
		<g fill="#262626" stroke="#404040" stroke-width="0.5">
			<circle cx="50" cy="9" r="6" />
			<rect x="44" y="15" width="12" height="4" rx="1" />
			<path d="M35 19 L65 19 L63 50 L37 50 Z" />
			<path d="M35 20 L28 21 L24 45 L29 46 L33 26 Z" />
			<path d="M65 20 L72 21 L76 45 L71 46 L67 26 Z" />
			<path d="M37 50 L63 50 L62 60 L38 60 Z" />
			<path d="M38 60 L48 60 L47 95 L40 95 Z" />
			<path d="M52 60 L62 60 L60 95 L53 95 Z" />
		</g>
		{#each sites as site (site.id)}
			<circle
				cx={Number(site.x)}
				cy={Number(site.y) * 1.2}
				r={selected === site.id ? 3.4 : 2.4}
				fill={colorFor(site)}
				stroke={selected === site.id ? '#fff' : 'none'}
				stroke-width="0.7"
			/>
		{/each}
	</svg>

	<!-- Accessible, keyboard-navigable site picker. -->
	<div class="mt-3 grid w-full grid-cols-2 gap-1.5">
		{#each sites as site (site.id)}
			<button
				type="button"
				onclick={() => pick(site)}
				class="flex items-center gap-2 rounded border px-2 py-1.5 text-left text-xs transition {selected ===
				site.id
					? 'border-indigo-500 bg-indigo-950/50'
					: 'border-neutral-800 hover:border-neutral-600'}"
			>
				<span class="h-2 w-2 shrink-0 rounded-full" style="background: {colorFor(site)}"></span>
				<span class="flex-1 truncate">{site.name}</span>
				{#if site.days_since != null}
					<span class="text-neutral-600">{Math.round(site.days_since)}d</span>
				{/if}
			</button>
		{/each}
	</div>

	<div class="mt-2 flex gap-4 text-xs text-neutral-400">
		<span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full" style="background:{SITE_COLORS.rested}"></span> Rested</span>
		<span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full" style="background:{SITE_COLORS.recovering}"></span> Recovering</span>
		<span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full" style="background:{SITE_COLORS.fresh}"></span> Recent</span>
	</div>
</div>
