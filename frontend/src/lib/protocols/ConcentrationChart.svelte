<script lang="ts">
	import type { ConcentrationPoint } from './api';

	let { points, unit = 'mg' }: { points: ConcentrationPoint[]; unit?: string } = $props();

	const W = 600;
	const H = 160;
	const pad = 28;

	const max = $derived(Math.max(1, ...points.map((p) => p.value)));

	function path(): string {
		if (points.length < 2) return '';
		const n = points.length;
		return points
			.map((p, i) => {
				const x = pad + (i / (n - 1)) * (W - 2 * pad);
				const y = H - pad - (p.value / max) * (H - 2 * pad);
				return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	}

	function label(iso: string): string {
		return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}
</script>

{#if points.length < 2}
	<p class="text-sm text-neutral-500">Not enough dose history to plot a curve yet.</p>
{:else}
	<svg viewBox={`0 0 ${W} ${H}`} class="w-full">
		<line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#404040" stroke-width="1" />
		<line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="#404040" stroke-width="1" />
		<path d={path()} fill="none" stroke="#6366f1" stroke-width="2" />
		<text x={pad} y={pad - 8} fill="#a3a3a3" font-size="10">{max.toFixed(0)} {unit} active</text>
		<text x={pad} y={H - 8} fill="#737373" font-size="9">{label(points[0].t)}</text>
		<text x={W - pad} y={H - 8} fill="#737373" font-size="9" text-anchor="end">
			{label(points[points.length - 1].t)}
		</text>
	</svg>
{/if}
