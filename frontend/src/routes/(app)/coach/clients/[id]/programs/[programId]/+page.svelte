<script lang="ts">
	import { page } from '$app/stores';
	import ProgramBuilder from '$lib/training/ProgramBuilder.svelte';

	const cid = $derived(Number($page.params.id));
	const pid = $derived(Number($page.params.programId));
</script>

{#key pid}
	<ProgramBuilder programId={pid} acting={cid} backHref={`/coach/clients/${cid}/plan`} />
{/key}
