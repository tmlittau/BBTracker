<script lang="ts">
	// Dependency-free SVG overlay of relative concentration curves for the cycle
	// plotter. One coloured line per compound over a day axis (labelled in weeks).
	import type { CompoundPlot } from './api';

	let { data }: { data: CompoundPlot } = $props();

	const PALETTE = [
		'#fb7185', '#60a5fa', '#34d399', '#fbbf24', '#a78bfa',
		'#f472b6', '#22d3ee', '#a3e635', '#fb923c', '#e879f9'
	];

	const W = 720;
	const H = 300;
	const padL = 36;
	const padR = 12;
	const padT = 12;
	const padB = 26;

	const horizon = $derived(data.horizon_days || 1);
	const allLevels = $derived(data.compounds.flatMap((c) => c.points.map((p) => p.level)));
	const maxLevel = $derived(Math.max(1e-6, ...allLevels));

	const x = (day: number) => padL + (day / horizon) * (W - padL - padR);
	const y = (level: number) => H - padB - (level / maxLevel) * (H - padT - padB);

	function linePath(points: { day: number; level: number }[]): string {
		return points
			.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day).toFixed(1)},${y(p.level).toFixed(1)}`)
			.join(' ');
	}

	// Weekly gridlines on the x-axis.
	const weeks = $derived(
		Array.from({ length: Math.floor(horizon / 7) + 1 }, (_, i) => i * 7).filter((d) => d <= horizon)
	);
	const color = (i: number) => PALETTE[i % PALETTE.length];
</script>

{#if data.compounds.length === 0}
	<p class="text-sm text-neutral-500">
		Add at least one mass-dosed compound to plot.{#if data.excluded.length}
			Not plotted: {data.excluded.join(', ')} (non-mass units or no half-life).{/if}
	</p>
{:else}
	<svg viewBox={`0 0 ${W} ${H}`} class="w-full" role="img" aria-label="Compound concentration curves">
		<!-- week gridlines + labels -->
		{#each weeks as d (d)}
			<line x1={x(d)} y1={padT} x2={x(d)} y2={H - padB} stroke="#262626" stroke-width="1" />
			<text x={x(d)} y={H - padB + 16} fill="#737373" font-size="10" text-anchor="middle">
				{d === 0 ? '0' : `w${d / 7}`}
			</text>
		{/each}
		<!-- y axis -->
		<line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#404040" stroke-width="1" />
		<text
			x={-(H / 2)}
			y={12}
			fill="#a3a3a3"
			font-size="10"
			text-anchor="middle"
			transform="rotate(-90)">Active level ({data.unit})</text
		>

		<!-- compound lines -->
		{#each data.compounds as c, i (c.compound_id)}
			<path d={linePath(c.points)} fill="none" stroke={color(i)} stroke-width="2" />
		{/each}
	</svg>

	<!-- legend -->
	<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
		{#each data.compounds as c, i (c.compound_id)}
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2 w-3 rounded-sm" style="background:{color(i)}"></span>
				{c.name}
				<span class="text-neutral-600">· t½ {(c.half_life_hours / 24).toFixed(1)} d</span>
			</span>
		{/each}
	</div>
	<p class="mt-2 text-xs text-neutral-500">
		Relative active serum level (Bateman absorption + elimination), comparable shapes — not calibrated
		ng/mL.{#if data.excluded.length}
			Not plotted: {data.excluded.join(', ')} (non-mass units or no half-life).{/if}
	</p>
{/if}
