<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { diaryApi, SCORE_FIELDS, type CheckIn } from '$lib/diary/api';
	import { todayISO, num } from '$lib/diary/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import ScoreRating from '$lib/components/ui/ScoreRating.svelte';

	// Themed rating symbol + colour per subjective scale.
	const SYMBOLS: Record<string, { symbol: string; color: string }> = {
		energy: { symbol: '⚡', color: 'text-amber-400' },
		sleep: { symbol: '😴', color: 'text-indigo-400' },
		mood: { symbol: '🙂', color: 'text-green-400' },
		motivation: { symbol: '🔥', color: 'text-orange-400' },
		soreness: { symbol: '💢', color: 'text-red-400' }
	};

	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let saved = $state(false);
	let existing = $state<CheckIn | null>(null);

	let date = $state($page.url.searchParams.get('date') ?? todayISO());
	let bodyweight = $state('');
	let scores = $state<Record<string, number | null>>({
		energy: null, sleep: null, mood: null, motivation: null, soreness: null
	});
	let notes = $state('');

	function hydrate(c: CheckIn) {
		existing = c;
		date = c.date;
		bodyweight = c.bodyweight ?? '';
		for (const f of SCORE_FIELDS) {
			scores[f.key] = (c[f.key] as number | null) ?? null;
		}
		notes = c.notes ?? '';
	}

	onMount(async () => {
		try {
			const all = await diaryApi.checkIns({ from: date, to: date });
			if (all.length) hydrate(all[0]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function payload() {
		return {
			date,
			// Bodyweight is mandatory; blank defaults to 0.
			bodyweight: bodyweight === '' ? '0' : String(num(bodyweight)),
			energy: scores.energy,
			sleep: scores.sleep,
			mood: scores.mood,
			motivation: scores.motivation,
			soreness: scores.soreness,
			notes
		};
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		saved = false;
		error = null;
		try {
			if (existing) hydrate(await diaryApi.updateCheckIn(existing.id, payload()));
			else hydrate(await diaryApi.createCheckIn(payload()));
			saved = true;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!existing || !confirm('Delete this check-in?')) return;
		await diaryApi.deleteCheckIn(existing.id);
		await goto('/diary');
	}
</script>

<a class="text-sm text-neutral-400 hover:text-white" href="/diary">← Diary</a>
<h1 class="mt-1 text-xl font-semibold">{existing ? 'Edit' : 'New'} check-in</h1>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else}
	<form class="mt-6 max-w-md space-y-5" onsubmit={save}>
		<div class="flex gap-3">
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="date">Date</label>
				<input id="date" name="date" type="date" bind:value={date} class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100" />
			</div>
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="bw">Bodyweight (kg) *</label>
				<input id="bw" name="bodyweight" type="number" step="0.1" required bind:value={bodyweight} placeholder="0" class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100" />
			</div>
		</div>

		<div>
			<p class="text-xs text-neutral-500">Subjective scores (tap to rate 1–5)</p>
			<div class="mt-2 space-y-2">
				{#each SCORE_FIELDS as f (f.key)}
					<div class="flex items-center justify-between">
						<span class="text-sm text-neutral-300">
							{f.label}{#if f.key === 'soreness'} <span class="text-neutral-600">(5 = very sore)</span>{/if}
						</span>
						<ScoreRating
							bind:value={scores[f.key]}
							symbol={SYMBOLS[f.key].symbol}
							color={SYMBOLS[f.key].color}
							label={f.label}
						/>
					</div>
				{/each}
			</div>
		</div>

		<div>
			<label class="text-xs text-neutral-500" for="notes">Notes (headspace, physical experience…)</label>
			<textarea id="notes" name="notes" rows="4" bind:value={notes} class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"></textarea>
		</div>

		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		{#if saved}<p class="text-sm text-green-400">Saved.</p>{/if}
		<div class="flex gap-2">
			<Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save check-in'}</Button>
			{#if existing}
				<button type="button" class="rounded-md border border-neutral-700 px-4 py-2 text-sm text-red-400 hover:border-red-500" onclick={remove}>Delete</button>
			{/if}
		</div>
	</form>
{/if}
