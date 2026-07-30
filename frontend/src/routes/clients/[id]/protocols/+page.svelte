<script lang="ts">
	import { page } from '$app/stores';
	import ProtocolBuilder from '$lib/clients/ProtocolBuilder.svelte';

	const clientId = $derived(Number($page.params.id));
</script>

<div class="p-6">
	{#key clientId}
		<ProtocolBuilder {clientId} />
	{/key}
</div>
