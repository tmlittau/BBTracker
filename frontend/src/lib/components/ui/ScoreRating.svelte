<script lang="ts">
	// A 1–max rating control rendered as themed symbols (like product-page stars,
	// but the symbol + colour are caller-supplied: ⚡ energy, 🌙 sleep, etc.).
	// Click a symbol to set the value; click the current value again to clear it.
	let {
		value = $bindable<number | null>(null),
		max = 5,
		symbol = '★',
		color = 'text-amber-400',
		label = '',
		readonly = false,
		onchange
	}: {
		value?: number | null;
		max?: number;
		symbol?: string;
		color?: string;
		label?: string;
		readonly?: boolean;
		onchange?: (v: number | null) => void;
	} = $props();

	function set(i: number) {
		if (readonly) return;
		value = value === i ? null : i;
		onchange?.(value);
	}
</script>

<div class="inline-flex items-center gap-1" role="group" aria-label={label}>
	{#each Array(max) as _, idx (idx)}
		{@const i = idx + 1}
		{@const on = value != null && i <= value}
		<button
			type="button"
			disabled={readonly}
			onclick={() => set(i)}
			class="text-xl leading-none transition-transform hover:scale-110 disabled:hover:scale-100 {on
				? `${color} opacity-100`
				: 'opacity-30 grayscale'}"
			aria-label={`${label} ${i} of ${max}`}
			aria-pressed={on}
		>
			{symbol}
		</button>
	{/each}
</div>
