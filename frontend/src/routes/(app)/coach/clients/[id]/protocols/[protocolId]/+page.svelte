<script lang="ts">
	import { page } from '$app/stores';
	import ProtocolBuilder from '$lib/protocols/ProtocolBuilder.svelte';

	const cid = $derived(Number($page.params.id));
	const pid = $derived(Number($page.params.protocolId));
</script>

{#key pid}
	<ProtocolBuilder protocolId={pid} acting={cid} backHref={`/coach/clients/${cid}/plan`} />
{/key}
