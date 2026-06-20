<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		type = 'button',
		disabled = false,
		onclick,
		href = undefined,
		variant = 'primary',
		size = 'md',
		full = true,
		children
	}: {
		type?: 'button' | 'submit';
		disabled?: boolean;
		onclick?: (e: MouseEvent) => void;
		href?: string;
		variant?: 'primary' | 'ghost';
		size?: 'md' | 'sm';
		full?: boolean;
		children: Snippet;
	} = $props();

	const base =
		'inline-flex items-center justify-center gap-2 rounded-full font-medium transition disabled:opacity-50';
	const sizes = { md: 'px-5 py-2.5 text-sm', sm: 'px-3.5 py-1.5 text-sm' };
	const variants = {
		primary: 'bg-brand text-white shadow-sm shadow-orange-900/30 hover:brightness-110',
		ghost: 'border border-neutral-700 text-neutral-200 hover:border-neutral-500 hover:text-white'
	};
	const cls = $derived(
		`${base} ${sizes[size]} ${variants[variant]} ${full ? 'w-full' : ''}`
	);
</script>

{#if href}
	<a {href} class={cls}>{@render children()}</a>
{:else}
	<button {type} {disabled} {onclick} class={cls}>{@render children()}</button>
{/if}
