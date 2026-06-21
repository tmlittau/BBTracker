<script lang="ts">
	import { page } from '$app/stores';
	import ProgramBuilder from '$lib/training/ProgramBuilder.svelte';
</script>

<ProgramBuilder programId={Number($page.params.id)} backHref="/training/programs" />
