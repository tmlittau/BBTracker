<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		href,
		children
	}: { href?: string; children: Snippet } = $props();
</script>

{#if href}
	<a
		{href}
		class="block rounded-lg border border-neutral-800 p-4 transition hover:border-neutral-600"
	>
		{@render children()}
	</a>
{:else}
	<div class="rounded-lg border border-neutral-800 p-4">
		{@render children()}
	</div>
{/if}
