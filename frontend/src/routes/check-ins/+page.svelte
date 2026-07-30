<script lang="ts">
	import { onMount } from 'svelte';
	import { coachingApi, type CheckInRow, type CheckInDetail } from '$lib/coaching/api';

	let rows = $state<CheckInRow[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let onlyPending = $state(false);

	let selectedId = $state<number | null>(null);
	let detail = $state<CheckInDetail | null>(null);
	let loadingDetail = $state(false);

	let feedback = $state('');
	let sending = $state(false);

	async function loadQueue(autoselect = true) {
		loading = true;
		error = null;
		try {
			rows = await coachingApi.checkIns({ pending: onlyPending });
			if (autoselect) {
				if (selectedId == null || !rows.some((r) => r.id === selectedId)) {
					if (rows[0]) await selectRow(rows[0].id);
					else {
						selectedId = null;
						detail = null;
					}
				}
			}
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function selectRow(id: number) {
		selectedId = id;
		loadingDetail = true;
		try {
			detail = await coachingApi.checkIn(id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loadingDetail = false;
		}
	}

	onMount(() => loadQueue());

	async function setFilter(v: boolean) {
		if (onlyPending === v) return;
		onlyPending = v;
		await loadQueue();
	}

	async function send() {
		if (!detail || !feedback.trim()) return;
		sending = true;
		error = null;
		const id = detail.check_in.id;
		try {
			await coachingApi.addCheckInComment(id, feedback.trim());
			feedback = '';
			detail = await coachingApi.checkIn(id);
			const row = rows.find((r) => r.id === id);
			if (row) {
				row.reviewed = true;
				row.comment_count = detail.comments.length;
			}
			if (onlyPending) await loadQueue(false); // it drops out of the pending list
		} catch (e) {
			error = (e as Error).message;
		} finally {
			sending = false;
		}
	}

	const fmtDate = (d: string) =>
		new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		});
	const score = (v: number | null | undefined) => (v == null ? '—' : `${v}/5`);
	const n1 = (v: number | null | undefined) => (v == null ? '—' : Number(v).toFixed(1));

	// bodyweight delta vs the previous check-in
	const bwDelta = $derived.by(() => {
		if (!detail || detail.check_in.bodyweight == null || detail.previous_bodyweight == null) return null;
		return Math.round((detail.check_in.bodyweight - detail.previous_bodyweight) * 10) / 10;
	});

	// tiny bodyweight sparkline from weight_series
	const spark = $derived.by(() => {
		const pts = (detail?.weight_series ?? []).filter((p) => p.bodyweight != null) as {
			date: string;
			bodyweight: number;
		}[];
		if (pts.length < 2) return null;
		const ws = pts.map((p) => p.bodyweight);
		const min = Math.min(...ws);
		const max = Math.max(...ws);
		const range = max - min || 1;
		const stepX = 100 / (pts.length - 1);
		const line = pts
			.map((p, i) => `${(i * stepX).toFixed(1)},${(26 - ((p.bodyweight - min) / range) * 24).toFixed(1)}`)
			.join(' ');
		return { line, count: pts.length };
	});

	const SUBJ = [
		['energy', 'Energy'],
		['sleep', 'Sleep'],
		['mood', 'Mood'],
		['motivation', 'Motivation'],
		['soreness', 'Soreness']
	] as const;
</script>

<div class="flex h-full">
	<!-- Queue -->
	<aside class="flex w-72 shrink-0 flex-col border-r border-neutral-800">
		<div class="border-b border-neutral-800 px-4 py-3">
			<h1 class="text-lg font-semibold">Check-ins</h1>
			<div class="mt-2 flex gap-1 text-xs">
				<button
					onclick={() => setFilter(false)}
					class="rounded-full px-2.5 py-1 {!onlyPending ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}"
				>
					All
				</button>
				<button
					onclick={() => setFilter(true)}
					class="rounded-full px-2.5 py-1 {onlyPending ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}"
				>
					Needs review
				</button>
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto">
			{#if loading}
				<p class="px-4 py-3 text-sm text-neutral-400">Loading…</p>
			{:else if rows.length === 0}
				<p class="px-4 py-3 text-sm text-neutral-500">
					{onlyPending ? 'Nothing to review — all caught up.' : 'No check-ins yet.'}
				</p>
			{:else}
				{#each rows as r (r.id)}
					<button
						onclick={() => selectRow(r.id)}
						class="flex w-full flex-col items-start gap-0.5 border-b border-neutral-900 px-4 py-2.5 text-left {selectedId === r.id
							? 'bg-neutral-800'
							: 'hover:bg-neutral-900'}"
					>
						<div class="flex w-full items-center justify-between">
							<span class="truncate text-sm font-medium text-neutral-100">{r.client_name}</span>
							{#if !r.reviewed}
								<span class="ml-2 h-2 w-2 shrink-0 rounded-full bg-orange-500" title="Needs review"></span>
							{/if}
						</div>
						<div class="flex w-full items-center justify-between text-xs text-neutral-500">
							<span>{fmtDate(r.date)}</span>
							<span class="tabular-nums">
								{r.bodyweight != null ? `${r.bodyweight} kg` : ''}
								{#if r.has_notes}· ✎{/if}
								{#if r.comment_count > 0}· 💬{r.comment_count}{/if}
							</span>
						</div>
					</button>
				{/each}
			{/if}
		</div>
	</aside>

	<!-- Review -->
	<section class="min-w-0 flex-1 overflow-y-auto p-6">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !detail}
			<p class="text-sm text-neutral-500">{loadingDetail ? 'Loading…' : 'Select a check-in to review.'}</p>
		{:else}
			{@const ci = detail.check_in}
			{@const wk = detail.weekly}
			<div class="flex items-center justify-between">
				<div>
					<h2 class="text-lg font-semibold">{detail.client.name}</h2>
					<p class="text-xs text-neutral-500">Check-in · {fmtDate(ci.date)}</p>
				</div>
				<a href={`/clients/${detail.client.id}`} class="text-sm text-orange-400 hover:text-orange-300">Open workspace →</a>
			</div>

			<!-- vitals + sparkline -->
			<div class="mt-4 grid gap-4 lg:grid-cols-3">
				<div class="rounded-lg border border-neutral-800 p-4">
					<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Bodyweight</h3>
					<div class="mt-1 flex items-baseline gap-2">
						<span class="text-2xl font-semibold tabular-nums">{ci.bodyweight != null ? ci.bodyweight : '—'}</span>
						<span class="text-sm text-neutral-500">kg</span>
						{#if bwDelta != null}
							<span class="text-xs {bwDelta > 0 ? 'text-amber-400' : bwDelta < 0 ? 'text-emerald-400' : 'text-neutral-500'}">
								{bwDelta > 0 ? '+' : ''}{bwDelta} vs last
							</span>
						{/if}
					</div>
					{#if spark}
						<svg viewBox="0 0 100 28" class="mt-2 h-8 w-full text-orange-400" preserveAspectRatio="none">
							<polyline points={spark.line} fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke" />
						</svg>
						<p class="text-[10px] text-neutral-600">last {spark.count} check-ins</p>
					{/if}
				</div>

				<div class="rounded-lg border border-neutral-800 p-4">
					<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Vitals</h3>
					<div class="mt-2 grid grid-cols-2 gap-y-1 text-sm">
						<span class="text-neutral-500">Blood pressure</span>
						<span class="text-right tabular-nums">{ci.systolic && ci.diastolic ? `${ci.systolic}/${ci.diastolic}` : '—'}</span>
						<span class="text-neutral-500">Pulse</span>
						<span class="text-right tabular-nums">{ci.pulse ?? '—'}</span>
					</div>
				</div>

				<div class="rounded-lg border border-neutral-800 p-4">
					<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Subjective (this day)</h3>
					<div class="mt-2 grid grid-cols-2 gap-y-1 text-sm">
						{#each SUBJ as [key, label] (key)}
							<span class="text-neutral-500">{label}</span>
							<span class="text-right tabular-nums">{score(ci[key])}</span>
						{/each}
					</div>
				</div>
			</div>

			{#if ci.notes}
				<div class="mt-4 rounded-lg border border-neutral-800 p-4">
					<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Client notes</h3>
					<p class="mt-1.5 whitespace-pre-wrap text-sm text-neutral-200">{ci.notes}</p>
				</div>
			{/if}

			<!-- the trailing week -->
			<div class="mt-4 rounded-lg border border-neutral-800 p-4">
				<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">
					Trailing week ({fmtDate(wk.start_date)} – {fmtDate(wk.end_date)})
				</h3>
				<div class="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
					<div><div class="text-neutral-500">Sessions</div><div class="tabular-nums">{wk.training.sessions} · {wk.training.working_sets} sets</div></div>
					<div><div class="text-neutral-500">PRs</div><div class="tabular-nums">{wk.training.prs}</div></div>
					<div><div class="text-neutral-500">Nutrition</div><div class="tabular-nums">{wk.nutrition.days_logged}/7 d logged</div></div>
					<div><div class="text-neutral-500">Avg intake</div><div class="tabular-nums">{n1(wk.nutrition.avg_calories)} kcal / {n1(wk.nutrition.avg_protein_g)}g P</div></div>
					<div><div class="text-neutral-500">Weight Δ (wk)</div><div class="tabular-nums">{wk.bodyweight ? `${wk.bodyweight.delta > 0 ? '+' : ''}${wk.bodyweight.delta} kg` : '—'}</div></div>
					<div><div class="text-neutral-500">Doses</div><div class="tabular-nums">{wk.doses}</div></div>
					<div><div class="text-neutral-500">Photos</div><div class="tabular-nums">{wk.photos}</div></div>
					<div><div class="text-neutral-500">Check-ins</div><div class="tabular-nums">{wk.check_ins}/7</div></div>
				</div>
				{#if wk.training.top_muscles?.length}
					<p class="mt-2 text-xs text-neutral-500">
						Top volume: {wk.training.top_muscles.map((m) => `${m.muscle} (${m.sets})`).join(' · ')}
					</p>
				{/if}
			</div>

			<!-- feedback thread -->
			<div class="mt-4 max-w-2xl">
				<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Feedback</h3>
				<div class="mt-2 space-y-2">
					{#each detail.comments as c (c.id)}
						<div class="rounded-lg border p-3 {c.by_coach ? 'border-orange-900/50 bg-orange-950/20' : 'border-neutral-800 bg-neutral-900'}">
							<div class="mb-0.5 flex items-center justify-between text-xs">
								<span class="font-medium {c.by_coach ? 'text-orange-300' : 'text-neutral-300'}">{c.author_name}{c.by_coach ? ' (coach)' : ''}</span>
								<span class="text-neutral-600">{new Date(c.created_at).toLocaleString()}</span>
							</div>
							<p class="whitespace-pre-wrap text-sm text-neutral-200">{c.body}</p>
						</div>
					{:else}
						<p class="text-sm text-neutral-500">No feedback yet — write the first note below.</p>
					{/each}
				</div>

				<div class="mt-3">
					<textarea
						bind:value={feedback}
						rows="3"
						placeholder="Feedback for this check-in — adjustments, encouragement, what to watch…"
						class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
					></textarea>
					<button
						onclick={send}
						disabled={sending || !feedback.trim()}
						class="mt-2 rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
					>
						{sending ? 'Sending…' : 'Send feedback'}
					</button>
				</div>
			</div>
		{/if}
	</section>
</div>
