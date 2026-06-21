<script lang="ts">
	import { page } from '$app/stores';
	import ProtocolBuilder from '$lib/protocols/ProtocolBuilder.svelte';
</script>

<ProtocolBuilder protocolId={Number($page.params.id)} backHref="/protocols/manage" />
