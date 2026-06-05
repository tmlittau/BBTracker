<script lang="ts">
	import type { Snippet } from 'svelte';

	// Reusable modal built on the native <dialog> element, which gives us a focus
	// trap, ESC-to-close, inert background, and a ::backdrop for free. Drive it
	// with the bindable `open` prop; closing (ESC, ✕, or backdrop click) flips
	// `open` to false and fires `onclose`.
	let {
		open = $bindable(false),
		title = '',
		size = 'md',
		onclose,
		children
	}: {
		open?: boolean;
		title?: string;
		size?: 'sm' | 'md' | 'lg';
		onclose?: () => void;
		children: Snippet;
	} = $props();

	let dialog = $state<HTMLDialogElement | null>(null);

	// Reflect `open` into the native dialog. showModal() handles the focus trap +
	// background inerting; close() tears it down. Guards avoid InvalidStateError.
	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) dialog.showModal();
		else if (!open && dialog.open) dialog.close();
	});

	function close() {
		open = false;
		onclose?.();
	}

	// ESC fires `cancel`; take it over so state stays in sync.
	function onCancel(e: Event) {
		e.preventDefault();
		close();
	}

	// With p-0 on the dialog, only a backdrop click has the dialog itself as target
	// (content clicks hit the inner panel) — so this closes on outside-click only.
	function onClick(e: MouseEvent) {
		if (e.target === dialog) close();
	}

	const widths = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-2xl' };
</script>

<dialog
	bind:this={dialog}
	oncancel={onCancel}
	onclick={onClick}
	class="m-auto w-[calc(100%-2rem)] {widths[size]} rounded-lg border border-neutral-700 bg-neutral-950 p-0 text-neutral-100 backdrop:bg-black/60"
>
	{#if open}
		<div class="max-h-[85vh] overflow-y-auto p-5">
			{#if title}
				<div class="mb-3 flex items-center justify-between gap-4">
					<h2 class="text-lg font-semibold">{title}</h2>
					<button
						type="button"
						class="shrink-0 text-neutral-500 hover:text-neutral-200"
						onclick={close}
						aria-label="Close"
					>
						✕
					</button>
				</div>
			{/if}
			{@render children()}
		</div>
	{/if}
</dialog>
