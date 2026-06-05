<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		type = 'button',
		disabled = false,
		onclick,
		children
	}: {
		type?: 'button' | 'submit';
		disabled?: boolean;
		onclick?: (e: MouseEvent) => void;
		children: Snippet;
	} = $props();
</script>

<button
	{type}
	{disabled}
	{onclick}
	class="w-full rounded-md bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
>
	{@render children()}
</button>
