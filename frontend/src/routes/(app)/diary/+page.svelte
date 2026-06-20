<script lang="ts">
	import { onMount } from 'svelte';
	import { diaryApi, SCORE_FIELDS, type CheckIn, type ProgressPhoto } from '$lib/diary/api';
	import { todayISO, wellbeingAverage, num } from '$lib/diary/calc';
	import Card from '$lib/components/ui/Card.svelte';
	import LineChart from '$lib/components/ui/LineChart.svelte';

	let checkIns = $state<CheckIn[]>([]);
	let recentPhotos = $state<ProgressPhoto[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			[checkIns, recentPhotos] = await Promise.all([diaryApi.checkIns(), diaryApi.photos()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	const hasToday = $derived(checkIns.some((c) => c.date === todayISO()));

	// Granular daily bodyweight + a 7-day rolling-average overlay.
	const daily = $derived(
		checkIns
			.filter((c) => c.bodyweight != null && num(c.bodyweight) > 0)
			.map((c) => ({ x: c.date, y: num(c.bodyweight) }))
			.sort((a, b) => (a.x < b.x ? -1 : 1))
	);
	const weeklyAvg = $derived(
		daily.map((p) => {
			const end = new Date(p.x + 'T00:00:00').getTime();
			const start = end - 6 * 86_400_000;
			const window = daily.filter((q) => {
				const t = new Date(q.x + 'T00:00:00').getTime();
				return t >= start && t <= end;
			});
			const avg = window.reduce((s, q) => s + q.y, 0) / window.length;
			return { x: p.x, y: Math.round(avg * 10) / 10 };
		})
	);
	const weightSeries = $derived([
		{ points: daily, color: '#6366f1', dots: true, label: 'daily' },
		{ points: weeklyAvg, color: '#f59e0b', dashed: true, label: '7-day avg' }
	]);

	// Blood pressure (systolic + diastolic), toggled with the bodyweight plot.
	let plotView = $state<'weight' | 'bp'>('weight');
	const bpReadings = $derived(
		checkIns
			.filter((c) => c.systolic != null && c.diastolic != null)
			.map((c) => ({ date: c.date, sys: c.systolic as number, dia: c.diastolic as number }))
			.sort((a, b) => (a.date < b.date ? -1 : 1))
	);
	const bpSeries = $derived([
		{ points: bpReadings.map((r) => ({ x: r.date, y: r.sys })), color: '#f43f5e', dots: true, label: 'systolic' },
		{ points: bpReadings.map((r) => ({ x: r.date, y: r.dia })), color: '#38bdf8', dots: true, label: 'diastolic' }
	]);
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Progress diary</h1>
	<a href="/diary/check-in" class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110">New check-in</a>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	{#if !hasToday}
		<div class="mt-6 rounded-lg border border-dashed border-neutral-700 p-4 text-sm text-neutral-400">
			No check-in for today yet.
			<a class="text-orange-400 hover:text-orange-300" href="/diary/check-in">Add one</a>
		</div>
	{/if}

	<!-- Bodyweight trend -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<div class="flex items-center justify-between">
			<div class="flex gap-1 text-sm">
				<button
					class="rounded px-2 py-0.5 {plotView === 'weight' ? 'bg-neutral-800 font-medium text-white' : 'text-neutral-400 hover:text-white'}"
					onclick={() => (plotView = 'weight')}
				>Bodyweight</button>
				<button
					class="rounded px-2 py-0.5 {plotView === 'bp' ? 'bg-neutral-800 font-medium text-white' : 'text-neutral-400 hover:text-white'}"
					onclick={() => (plotView = 'bp')}
				>Blood pressure</button>
			</div>
			{#if plotView === 'weight'}
				<span class="text-xs text-neutral-500">
					<span class="text-indigo-400">daily</span> · <span class="text-amber-400">7-day avg</span>
				</span>
			{:else}
				<span class="text-xs text-neutral-500">
					<span class="text-rose-400">systolic</span> · <span class="text-sky-400">diastolic</span>
				</span>
			{/if}
		</div>
		{#if plotView === 'weight'}
			{#if daily.length === 0}
				<p class="mt-3 text-sm text-neutral-500">Log bodyweight in your check-ins to see the trend.</p>
			{:else}
				<div class="mt-3"><LineChart series={weightSeries} unit="kg" /></div>
			{/if}
		{:else if bpReadings.length === 0}
			<p class="mt-3 text-sm text-neutral-500">Log blood pressure in your check-ins to see the trend.</p>
		{:else}
			<div class="mt-3"><LineChart series={bpSeries} unit="mmHg" /></div>
		{/if}
	</section>

	<section class="mt-6">
		<h2 class="font-medium">Recent check-ins</h2>
		{#if checkIns.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No check-ins yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each checkIns.slice(0, 10) as c (c.id)}
					{@const avg = wellbeingAverage([c.energy, c.sleep, c.mood, c.motivation])}
					<Card href={`/diary/check-in?date=${c.date}`}>
						<div class="flex items-center justify-between">
							<span class="font-medium">{c.date}</span>
							<span class="text-xs text-neutral-500">
								{#if c.bodyweight}{num(c.bodyweight)} kg · {/if}
								{#if avg !== null}wellbeing {avg}/5{:else}no scores{/if}
							</span>
						</div>
						{#if c.notes}<p class="mt-1 truncate text-xs text-neutral-500">{c.notes}</p>{/if}
					</Card>
				{/each}
			</div>
		{/if}
	</section>

	<section class="mt-8">
		<h2 class="font-medium">Recent photos</h2>
		{#if recentPhotos.length === 0}
			<p class="mt-2 text-sm text-neutral-500">
				No photos yet. <a class="text-orange-400 hover:text-orange-300" href="/diary/photos">Upload your first</a>
			</p>
		{:else}
			<div class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
				{#each recentPhotos.slice(0, 8) as photo (photo.id)}
					<a href="/diary/photos" class="block">
						<img src={photo.thumb_url} alt={`${photo.pose_name || 'Photo'} ${photo.taken_on}`} class="aspect-[3/4] w-full rounded object-cover" loading="lazy" />
						<span class="mt-1 block truncate text-[10px] text-neutral-500">{photo.pose_name || '—'} · {photo.taken_on}</span>
					</a>
				{/each}
			</div>
		{/if}
		<p class="mt-2 text-xs text-neutral-600">
			{SCORE_FIELDS.length} subjective scales tracked per check-in; photos are private to your account.
		</p>
	</section>
{/if}
