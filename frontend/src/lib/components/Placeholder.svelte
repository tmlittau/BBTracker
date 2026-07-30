<script lang="ts">
	let { title, note }: { title: string; note: string } = $props();
</script>

<div class="p-6">
	<h1 class="text-xl font-semibold">{title}</h1>
	<p class="mt-2 max-w-xl text-sm text-neutral-500">{note}</p>
</div>
