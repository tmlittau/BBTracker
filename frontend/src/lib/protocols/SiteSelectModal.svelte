<script lang="ts">
	// Compact injection-site picker for quick-logging an injectable dose. Wraps the
	// BodyMap (recency-coloured) + the rotation suggestion, then hands the chosen
	// site id (or null) back via onconfirm.
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import BodyMap from '$lib/protocols/BodyMap.svelte';
	import type { SiteRecency } from '$lib/protocols/api';

	let {
		open = $bindable(false),
		sites,
		suggestion = null,
		title = 'Injection site',
		onconfirm
	}: {
		open?: boolean;
		sites: SiteRecency[];
		suggestion?: SiteRecency | null;
		title?: string;
		onconfirm: (siteId: number | null) => void;
	} = $props();

	let selected = $state<number | null>(null);

	// Preselect the rotation suggestion when the modal opens.
	$effect(() => {
		if (open && selected == null && suggestion?.id) selected = suggestion.id;
	});

	function log() {
		const id = selected;
		open = false;
		selected = null;
		onconfirm(id);
	}
</script>

<Modal bind:open {title} size="md">
	<p class="text-xs text-neutral-500">Pick the injection site for rotation tracking.</p>
	{#if suggestion?.name}
		<button
			type="button"
			class="mt-2 text-xs text-indigo-400 hover:text-indigo-300"
			onclick={() => (selected = suggestion?.id ?? null)}
		>
			Use suggested: {suggestion.name}
		</button>
	{/if}
	<div class="mt-2"><BodyMap {sites} bind:selected /></div>
	<div class="mt-3 flex items-center gap-3">
		<Button onclick={log}>{selected ? 'Log here' : 'Log without site'}</Button>
		<button type="button" class="text-sm text-neutral-400 hover:text-white" onclick={() => (open = false)}>
			Cancel
		</button>
	</div>
</Modal>
