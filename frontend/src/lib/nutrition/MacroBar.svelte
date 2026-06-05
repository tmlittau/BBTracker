<script lang="ts">
	import { barWidth, macroColor, num, pct } from './calc';
	import type { SummaryNutrient } from './api';

	// `color` (a tailwind bg-* class) gives each macro its own hue; when omitted we
	// fall back to the red/amber/green status colour (used for non-macro bars).
	let {
		nutrient,
		big = false,
		color
	}: { nutrient: SummaryNutrient | undefined; big?: boolean; color?: string } = $props();

	const amount = $derived(nutrient ? num(nutrient.amount) : 0);
	const target = $derived(nutrient?.target != null ? num(nutrient.target) : null);
	const percent = $derived(nutrient?.percent ?? pct(amount, target));
	const statusColor = $derived(macroColor(percent));

	const colors: Record<string, string> = {
		green: 'bg-green-600',
		amber: 'bg-amber-500',
		red: 'bg-red-600',
		none: 'bg-indigo-600'
	};
	const barClass = $derived(color ?? colors[statusColor]);
</script>

<div>
	<div class="flex items-baseline justify-between text-sm">
		<span class={big ? 'font-medium' : 'text-neutral-300'}>{nutrient?.name ?? '—'}</span>
		<span class="text-neutral-400">
			{amount.toFixed(big ? 0 : 1)}{#if target}<span class="text-neutral-600"> / {target.toFixed(0)} {nutrient?.unit}</span>{:else}<span class="text-neutral-600"> {nutrient?.unit ?? ''}</span>{/if}
		</span>
	</div>
	<div class="mt-1 h-2 w-full overflow-hidden rounded-full bg-neutral-800">
		<div class="h-2 rounded-full {barClass}" style="width: {barWidth(percent)}%"></div>
	</div>
</div>
