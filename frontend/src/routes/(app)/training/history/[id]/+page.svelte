<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { trainingApi, type WorkoutSession } from '$lib/training/api';
	import { formatHM, durationSeconds } from '$lib/training/calc';
	import Card from '$lib/components/ui/Card.svelte';

	const sessionId = Number($page.params.id);

	let session = $state<WorkoutSession | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			session = await trainingApi.session(sessionId);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	const completedSets = (le: WorkoutSession['logged_exercises'][number]) =>
		le.sets.filter((s) => s.is_completed);
	const totalSets = $derived(
		session?.logged_exercises.reduce((n, le) => n + completedSets(le).length, 0) ?? 0
	);
</script>

<a class="text-sm text-neutral-400 hover:text-white" href="/training/history">← History</a>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if session}
	<div class="mt-1">
		<h1 class="text-xl font-semibold">{session.name || 'Workout'}</h1>
		<p class="mt-1 text-sm text-neutral-500">
			{new Date(session.started_at).toLocaleString()}
			{#if session.is_completed && session.ended_at}
				· ⏱ {formatHM(durationSeconds(session.started_at, session.ended_at))}
			{:else}
				· <span class="text-amber-400">in progress</span>
			{/if}
			· {session.logged_exercises.length} exercise(s) · {totalSets} set(s)
			{#if session.bodyweight}· BW {session.bodyweight} kg{/if}
		</p>
	</div>

	{#if session.logged_exercises.length === 0}
		<p class="mt-6 text-neutral-500">No exercises logged in this session.</p>
	{:else}
		<div class="mt-5 space-y-4">
			{#each session.logged_exercises as le (le.id)}
				<Card>
					<h2 class="font-medium">{le.exercise_name}</h2>
					{#if completedSets(le).length === 0}
						<p class="mt-1 text-xs text-neutral-500">No completed sets.</p>
					{:else}
						<table class="mt-2 w-full text-sm">
							<thead class="text-xs text-neutral-500">
								<tr>
									<th class="w-6 text-left font-normal">#</th>
									<th class="text-left font-normal">Type</th>
									<th class="text-right font-normal">Weight</th>
									<th class="text-right font-normal">Reps</th>
									<th class="text-right font-normal">e1RM</th>
								</tr>
							</thead>
							<tbody>
								{#each completedSets(le) as s, i (s.id)}
									<tr class="border-t border-neutral-800">
										<td class="py-1 text-neutral-500">{i + 1}</td>
										<td class="py-1">
											{s.set_type}
											{#if s.is_pr}<span class="ml-1 rounded bg-yellow-900 px-1 text-xs text-yellow-300">PR</span>{/if}
										</td>
										<td class="py-1 text-right tabular-nums">{s.weight ?? '—'}</td>
										<td class="py-1 text-right tabular-nums">{s.reps ?? '—'}</td>
										<td class="py-1 text-right tabular-nums text-neutral-500">{s.e1rm ?? '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</Card>
			{/each}
		</div>
	{/if}

	{#if session.notes}
		<p class="mt-4 text-sm text-neutral-400">{session.notes}</p>
	{/if}
{/if}
