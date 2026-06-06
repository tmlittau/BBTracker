<script lang="ts">
	// Numeric field with big −/+ steppers for one-handed entry at the gym. The
	// input carries `aria-label={label}` so tests/screen-readers can target it;
	// the stepper buttons use neutral labels so they don't collide with it.
	let {
		value = $bindable(''),
		step = 1,
		min = 0,
		label = '',
		placeholder = '',
		inputmode = 'decimal'
	}: {
		value?: string;
		step?: number;
		min?: number;
		label?: string;
		placeholder?: string;
		inputmode?: 'decimal' | 'numeric';
	} = $props();

	function bump(delta: number) {
		const base = value === '' || value == null ? 0 : Number(value);
		if (Number.isNaN(base)) return;
		value = String(Math.max(min, Math.round((base + delta) * 100) / 100));
	}
</script>

<div>
	{#if label}<span class="text-xs text-neutral-500">{label}</span>{/if}
	<div class="mt-1 flex items-stretch overflow-hidden rounded-md border border-neutral-700">
		<button
			type="button"
			class="w-11 shrink-0 bg-neutral-900 text-xl leading-none text-neutral-300 hover:bg-neutral-800 active:bg-neutral-700"
			aria-label="decrease"
			onclick={() => bump(-step)}
		>
			−
		</button>
		<input
			type="number"
			{inputmode}
			step={String(step)}
			{min}
			{placeholder}
			aria-label={label}
			bind:value
			class="w-full min-w-0 border-x border-neutral-700 bg-neutral-900 px-1 py-2 text-center text-neutral-100 outline-none focus:border-indigo-500"
		/>
		<button
			type="button"
			class="w-11 shrink-0 bg-neutral-900 text-xl leading-none text-neutral-300 hover:bg-neutral-800 active:bg-neutral-700"
			aria-label="increase"
			onclick={() => bump(step)}
		>
			+
		</button>
	</div>
</div>
