<script lang="ts">
	// Injection-site picker for quick-logging an injectable. Shows the sites for the
	// dose's route (IM vs SubQ) as a recency-coloured button grid, preselecting the
	// rotation suggestion, then hands the chosen site id (or null) back via onconfirm.
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import type { SiteRecency } from '$lib/protocols/api';

	let {
		open = $bindable(false),
		sites,
		suggestion = null,
		route = '',
		compound = '',
		title = 'Injection site',
		onconfirm
	}: {
		open?: boolean;
		sites: SiteRecency[];
		suggestion?: SiteRecency | null;
		route?: string;
		compound?: string;
		title?: string;
		onconfirm: (siteId: number | null) => void;
	} = $props();

	let selected = $state<number | null>(null);

	// Only the sites for this injection's route (im / subq); fall back to all.
	const shown = $derived(route ? sites.filter((s) => s.route === route) : sites);
	const suggestable = $derived(!!suggestion?.id && shown.some((s) => s.id === suggestion?.id));

	// Preselect the rotation suggestion (when it's valid for this route).
	$effect(() => {
		if (open && selected == null && suggestable) selected = suggestion?.id ?? null;
	});

	const DOT: Record<string, string> = {
		rested: 'bg-green-500',
		recovering: 'bg-amber-500',
		fresh: 'bg-red-500'
	};

	function log() {
		const id = selected;
		open = false;
		selected = null;
		onconfirm(id);
	}
	function cancel() {
		open = false;
		selected = null;
	}
</script>

<Modal bind:open {title} size="md">
	<p class="text-xs text-neutral-500">
		Pick where you injected{#if compound} <span class="text-neutral-300">{compound}</span>{/if} — for
		rotation tracking.{#if route} <span class="uppercase text-neutral-400">· {route}</span>{/if}
	</p>
	{#if suggestable}
		<button
			type="button"
			class="mt-2 text-xs text-indigo-400 hover:text-indigo-300"
			onclick={() => (selected = suggestion?.id ?? null)}
		>
			Use suggested: {suggestion?.name}
		</button>
	{/if}

	{#if shown.length === 0}
		<p class="mt-3 text-sm text-neutral-500">No injection sites configured for this route.</p>
	{:else}
		<div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
			{#each shown as s (s.id)}
				<button
					type="button"
					onclick={() => (selected = selected === s.id ? null : s.id)}
					class="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm {selected ===
					s.id
						? 'border-indigo-500 bg-indigo-950/40 text-white'
						: 'border-neutral-700 text-neutral-200 hover:border-neutral-500'}"
				>
					<span>{s.name}</span>
					<span
						class="h-2 w-2 shrink-0 rounded-full {DOT[s.status] ?? 'bg-neutral-600'}"
						title={s.days_since != null ? `${s.days_since} d ago` : 'not used recently'}
					></span>
				</button>
			{/each}
		</div>
		<p class="mt-2 text-[10px] text-neutral-600">
			Dot = recency (<span class="text-green-400">rested</span> /
			<span class="text-amber-400">recovering</span> /
			<span class="text-red-400">recent</span>).
		</p>
	{/if}

	<div class="mt-4 flex items-center gap-3">
		<Button onclick={log}>{selected ? 'Log here' : 'Log without site'}</Button>
		<button type="button" class="text-sm text-neutral-400 hover:text-white" onclick={cancel}>
			Cancel
		</button>
	</div>
</Modal>
