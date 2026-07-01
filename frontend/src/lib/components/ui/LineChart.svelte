<script lang="ts">
	// Small dependency-free SVG line chart (generalized from ConcentrationChart).
	// Plots one or more time series on a shared time axis, with an optional shaded
	// reference band (e.g. bloodwork normal range) and optional point dots. Used by
	// the bodyweight plot (daily + weekly-average overlay) and the bloodwork diagram.
	interface Pt {
		x: string; // ISO date / datetime
		y: number;
	}
	interface Series {
		points: Pt[];
		color?: string;
		dashed?: boolean;
		dots?: boolean;
		label?: string;
	}

	interface Marker {
		x: string; // ISO date
		label?: string;
		color?: string;
	}

	let {
		series,
		band,
		markers = [],
		unit = '',
		height = 180,
		baselineZero = false
	}: {
		series: Series[];
		band?: { low: number | null; high: number | null };
		markers?: Marker[];
		unit?: string;
		height?: number;
		baselineZero?: boolean;
	} = $props();

	const W = 600;
	const pad = 32;

	const allPts = $derived(series.flatMap((s) => s.points));
	const xs = $derived(allPts.map((p) => new Date(p.x).getTime()));
	const ys = $derived(allPts.map((p) => p.y));
	const bandVals = $derived(
		[band?.low, band?.high].filter((v) => v != null && Number.isFinite(v)) as number[]
	);

	const xMin = $derived(xs.length ? Math.min(...xs) : 0);
	const xMax = $derived(xs.length ? Math.max(...xs) : 1);

	const yLo = $derived(Math.min(...ys, ...bandVals, baselineZero ? 0 : Infinity));
	const yHi = $derived(Math.max(...ys, ...bandVals, baselineZero ? 0 : -Infinity));
	const yPad = $derived((yHi - yLo) * 0.08 || 1);
	const yMin = $derived(baselineZero ? 0 : yLo - yPad);
	const yMax = $derived(yHi + yPad);

	function sx(t: number): number {
		return xMax === xMin ? W / 2 : pad + ((t - xMin) / (xMax - xMin)) * (W - 2 * pad);
	}
	function sy(v: number): number {
		return yMax === yMin ? height / 2 : height - pad - ((v - yMin) / (yMax - yMin)) * (height - 2 * pad);
	}
	function pathFor(pts: Pt[]): string {
		return pts
			.map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(new Date(p.x).getTime()).toFixed(1)},${sy(p.y).toFixed(1)}`)
			.join(' ');
	}
	function label(iso: string): string {
		return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}
</script>

{#if allPts.length === 0}
	<p class="text-sm text-neutral-500">No data to plot yet.</p>
{:else}
	<svg viewBox={`0 0 ${W} ${height}`} class="w-full" role="img" aria-label="line chart">
		<!-- Reference band -->
		{#if band && band.low != null && band.high != null}
			<rect
				x={pad}
				y={sy(band.high)}
				width={W - 2 * pad}
				height={Math.max(0, sy(band.low) - sy(band.high))}
				fill="#22c55e"
				opacity="0.08"
			/>
		{/if}
		<!-- Axes -->
		<line x1={pad} y1={height - pad} x2={W - pad} y2={height - pad} stroke="#404040" stroke-width="1" />
		<line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#404040" stroke-width="1" />

		<!-- Vertical annotation markers (phase / protocol changes) -->
		{#each markers as m (m.x + (m.label ?? ''))}
			{@const mx = sx(new Date(m.x).getTime())}
			{#if mx >= pad && mx <= W - pad}
				<line x1={mx} y1={pad} x2={mx} y2={height - pad} stroke={m.color ?? '#f59e0b'} stroke-width="1" stroke-dasharray="3 3" opacity="0.55" />
				{#if m.label}<text x={mx + 2} y={pad + 8} fill={m.color ?? '#f59e0b'} font-size="8">{m.label}</text>{/if}
			{/if}
		{/each}

		{#each series as s (s.label ?? s.color)}
			{#if s.points.length >= 2}
				<path
					d={pathFor(s.points)}
					fill="none"
					stroke={s.color ?? '#6366f1'}
					stroke-width="2"
					stroke-dasharray={s.dashed ? '4 3' : undefined}
				/>
			{/if}
			{#if s.dots ?? s.points.length < 2}
				{#each s.points as p (p.x)}
					<circle cx={sx(new Date(p.x).getTime())} cy={sy(p.y)} r="2.5" fill={s.color ?? '#6366f1'} />
				{/each}
			{/if}
		{/each}

		<!-- y range + unit -->
		<text x={pad} y={pad - 8} fill="#a3a3a3" font-size="10">{yMax.toFixed(1)} {unit}</text>
		<text x={pad} y={height - pad + 14} fill="#737373" font-size="10">{yMin.toFixed(1)}</text>
		<!-- x ends -->
		<text x={pad} y={height - 6} fill="#737373" font-size="9">{label(allPts[0].x)}</text>
		<text x={W - pad} y={height - 6} fill="#737373" font-size="9" text-anchor="end">
			{label(allPts[allPts.length - 1].x)}
		</text>
	</svg>
{/if}
