<script lang="ts">
	// Dependency-free SVG chart of per-compound estimated serum concentration (Bateman
	// absorption + elimination) over a whole protocol. One coloured line per compound;
	// the logged-doses portion (≤ today) is solid and the schedule-projected portion
	// (> today) is dashed, split at a "today" marker. Data: GET /protocols/{id}/release/.
	import type { ProtocolRelease, ReleaseCompound } from './api';

	let { data }: { data: ProtocolRelease } = $props();

	const PALETTE = [
		'#6366f1', // indigo
		'#10b981', // emerald
		'#f59e0b', // amber
		'#38bdf8', // sky
		'#f43f5e', // rose
		'#a78bfa', // violet
		'#84cc16', // lime
		'#fb923c' // orange
	];

	const W = 720;
	const H = 300;
	const padL = 46;
	const padR = 14;
	const padT = 12;
	const padB = 34;

	const compounds = $derived(data.compounds);
	const allPts = $derived(compounds.flatMap((c) => c.points));
	const maxDay = $derived(Math.max(1, ...allPts.map((p) => p.day)));
	const maxRate = $derived(Math.max(1, ...allPts.map((p) => p.rate)));
	const todayDay = $derived(data.today_day);
	const showNow = $derived(todayDay >= 0 && todayDay <= maxDay);

	const x = (day: number) => padL + (day / maxDay) * (W - padL - padR);
	const y = (rate: number) => H - padB - (rate / maxRate) * (H - padT - padB);
	const color = (i: number) => PALETTE[i % PALETTE.length];

	function linePath(pts: { day: number; rate: number }[]): string {
		if (pts.length < 2) return '';
		return pts
			.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day).toFixed(1)},${y(p.rate).toFixed(1)}`)
			.join(' ');
	}

	const solid = (c: ReleaseCompound) => c.points.filter((p) => p.day <= todayDay);
	const projected = (c: ReleaseCompound) => c.points.filter((p) => p.day >= todayDay);

	const yTicks = $derived([1, 0.75, 0.5, 0.25, 0].map((f) => maxRate * f));
	const xStep = $derived(maxDay <= 35 ? 7 : maxDay <= 100 ? 14 : 28);
	const xTicks = $derived(
		Array.from({ length: Math.floor(maxDay / xStep) + 1 }, (_, i) => i * xStep)
	);

	const cy = padT + (H - padT - padB) / 2;

	function fmt(v: number): string {
		if (v === 0) return '0';
		return v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2);
	}
</script>

{#if compounds.length === 0}
	<p class="text-sm text-neutral-500">
		No release curve yet — add an injectable compound (dosed in mg or µg) with a schedule, or log a
		dose.{#if data.excluded.length}
			Not plotted: {data.excluded.join(', ')} (non-mass units).{/if}
	</p>
{:else}
	<svg viewBox={`0 0 ${W} ${H}`} class="w-full" role="img" aria-label="Protocol release curves">
		<!-- horizontal gridlines + y labels -->
		{#each yTicks as t (t)}
			<line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)} stroke="#262626" stroke-width="1" />
			<text x={padL - 6} y={y(t) + 3} fill="#737373" font-size="10" text-anchor="end">{fmt(t)}</text>
		{/each}

		<!-- x ticks -->
		{#each xTicks as d (d)}
			<text x={x(d)} y={H - padB + 14} fill="#737373" font-size="10" text-anchor="middle">{d}</text>
		{/each}
		<text x={(padL + W - padR) / 2} y={H - 2} fill="#a3a3a3" font-size="10" text-anchor="middle">
			Day
		</text>
		<text
			x="12"
			y={cy}
			fill="#a3a3a3"
			font-size="10"
			text-anchor="middle"
			transform={`rotate(-90 12 ${cy})`}
		>
			Est. serum level
		</text>

		<!-- today marker -->
		{#if showNow}
			<line
				x1={x(todayDay)}
				y1={padT}
				x2={x(todayDay)}
				y2={H - padB}
				stroke="#525252"
				stroke-width="1"
				stroke-dasharray="3 3"
			/>
			<text x={x(todayDay) + 3} y={padT + 9} fill="#a3a3a3" font-size="9">today</text>
		{/if}

		<!-- compound lines: solid = logged, dashed = projected -->
		{#each compounds as c, i (c.compound_id)}
			<path d={linePath(solid(c))} fill="none" stroke={color(i)} stroke-width="2" />
			<path
				d={linePath(projected(c))}
				fill="none"
				stroke={color(i)}
				stroke-width="2"
				stroke-dasharray="4 3"
				opacity="0.85"
			/>
		{/each}

		<!-- axes -->
		<line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="#404040" stroke-width="1" />
		<line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#404040" stroke-width="1" />
	</svg>

	<div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
		{#each compounds as c, i (c.compound_id)}
			<span class="inline-flex items-center gap-1.5">
				<span class="inline-block h-0.5 w-4 rounded" style={`background:${color(i)}`}></span>
				<span class="text-neutral-300">{c.name}</span>
				<span class="text-neutral-600">t½ {(c.half_life_hours / 24).toFixed(1)}d</span>
			</span>
		{/each}
	</div>
	<p class="mt-1 text-xs text-neutral-500">
		Solid = logged doses · dashed = projected from the schedule. Estimated serum concentration
		(one-compartment model from dose, ester fraction, bioavailability + half-life) — realistic shape,
		approximate scale.{#if data.excluded.length}
			Not plotted: {data.excluded.join(', ')} (non-mass units).{/if}
	</p>
{/if}
