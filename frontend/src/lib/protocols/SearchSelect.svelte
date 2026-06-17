<script lang="ts">
	// Dependency-free searchable select (combobox) with optional type-filter chips.
	// Used by the protocol builder to pick a compound/supplement from a long list:
	// type to search, tap a chip to filter by class. Generic over numeric ids.
	interface Option {
		id: number;
		label: string;
		group?: string; // used by the chip filter (e.g. compound_class)
		badge?: string; // small trailing hint (e.g. ester)
	}

	let {
		options,
		value = $bindable(),
		placeholder = 'Search…',
		groups = []
	}: {
		options: Option[];
		value: number | null;
		placeholder?: string;
		groups?: { key: string; label: string }[];
	} = $props();

	let query = $state('');
	let activeGroup = $state<string | null>(null);
	let open = $state(false);
	let highlight = $state(0);
	let root = $state<HTMLDivElement>();

	const selected = $derived(options.find((o) => o.id === value) ?? null);
	const filtered = $derived(
		options.filter(
			(o) =>
				(activeGroup == null || o.group === activeGroup) &&
				o.label.toLowerCase().includes(query.trim().toLowerCase())
		)
	);

	// Keep the highlighted row in range as the filter narrows.
	$effect(() => {
		void filtered.length;
		if (highlight >= filtered.length) highlight = 0;
	});

	function choose(o: Option) {
		value = o.id;
		query = '';
		open = false;
	}
	function clear() {
		value = null;
		query = '';
		open = true;
	}
	function onKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			open = true;
			highlight = Math.min(highlight + 1, filtered.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlight = Math.max(highlight - 1, 0);
		} else if (e.key === 'Enter') {
			if (open && filtered[highlight]) {
				e.preventDefault();
				choose(filtered[highlight]);
			}
		} else if (e.key === 'Escape') {
			open = false;
		}
	}
	function onWindowClick(e: MouseEvent) {
		if (root && !root.contains(e.target as Node)) open = false;
	}
</script>

<svelte:window onclick={onWindowClick} />

<div class="relative" bind:this={root}>
	<div
		class="flex items-center gap-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 focus-within:border-indigo-500"
	>
		<input
			class="w-full bg-transparent text-sm text-neutral-100 outline-none placeholder:text-neutral-500"
			{placeholder}
			value={open ? query : (selected?.label ?? '')}
			oninput={(e) => {
				query = e.currentTarget.value;
				open = true;
			}}
			onfocus={() => (open = true)}
			onkeydown={onKey}
		/>
		{#if selected}
			<button
				type="button"
				class="shrink-0 text-neutral-500 hover:text-neutral-300"
				aria-label="Clear selection"
				onclick={clear}>✕</button
			>
		{/if}
		<span class="shrink-0 text-neutral-600">▾</span>
	</div>

	{#if open}
		<div
			class="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-neutral-700 bg-neutral-900 shadow-lg"
		>
			{#if groups.length}
				<div
					class="sticky top-0 flex flex-wrap gap-1 border-b border-neutral-800 bg-neutral-900 p-1.5"
				>
					<button
						type="button"
						class="rounded-full px-2 py-0.5 text-xs {activeGroup == null
							? 'bg-indigo-600 text-white'
							: 'border border-neutral-700 text-neutral-300'}"
						onclick={() => (activeGroup = null)}>All</button
					>
					{#each groups as g (g.key)}
						<button
							type="button"
							class="rounded-full px-2 py-0.5 text-xs {activeGroup === g.key
								? 'bg-indigo-600 text-white'
								: 'border border-neutral-700 text-neutral-300'}"
							onclick={() => (activeGroup = g.key)}>{g.label}</button
						>
					{/each}
				</div>
			{/if}

			{#if filtered.length === 0}
				<p class="px-3 py-2 text-sm text-neutral-500">No matches.</p>
			{:else}
				<ul>
					{#each filtered as o, i (o.id)}
						<li>
							<button
								type="button"
								class="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm {i ===
								highlight
									? 'bg-neutral-800'
									: ''} {o.id === value ? 'text-indigo-300' : 'text-neutral-100'}"
								onmouseenter={() => (highlight = i)}
								onclick={() => choose(o)}
							>
								<span class="truncate">{o.label}</span>
								{#if o.badge}<span class="shrink-0 text-xs text-neutral-500">{o.badge}</span>{/if}
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}
</div>
