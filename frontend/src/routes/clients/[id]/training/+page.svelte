<script lang="ts">
	import { page } from '$app/stores';
	import ProgramBuilder from '$lib/clients/ProgramBuilder.svelte';

	const clientId = $derived(Number($page.params.id));
</script>

<div class="p-6">
	{#key clientId}
		<ProgramBuilder {clientId} />
	{/key}
</div>
