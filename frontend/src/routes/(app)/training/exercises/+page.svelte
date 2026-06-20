<script lang="ts">
	import { onMount } from 'svelte';
	import { trainingApi, type Exercise, type Muscle } from '$lib/training/api';
	import { apiErrorMessage } from '$lib/api/errors';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	let exercises = $state<Exercise[]>([]);
	let muscles = $state<Muscle[]>([]);
	let query = $state('');
	let loading = $state(true);
	let error = $state<string | null>(null);

	let showForm = $state(false);
	let editingId = $state<number | null>(null);
	let newName = $state('');
	let newCategory = $state('barbell');
	let selectedMuscles = $state<number[]>([]);
	let saving = $state(false);

	const categories = [
		'barbell', 'dumbbell', 'machine', 'cable', 'bodyweight', 'smith', 'kettlebell', 'banded', 'other'
	];

	async function load() {
		loading = true;
		try {
			exercises = await trainingApi.exercises(query);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(async () => {
		muscles = await trainingApi.muscles().catch(() => []);
		await load();
	});

	let searchTimer: ReturnType<typeof setTimeout>;
	function onSearch() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(load, 200);
	}

	function startNew() {
		editingId = null;
		newName = '';
		newCategory = 'barbell';
		selectedMuscles = [];
		showForm = true;
	}
	function startEdit(ex: Exercise) {
		editingId = ex.id;
		newName = ex.name;
		newCategory = ex.category;
		selectedMuscles = [...ex.primary_muscles];
		showForm = true;
	}
	function cancelForm() {
		showForm = false;
		editingId = null;
		newName = '';
	}
	function toggleMuscle(id: number) {
		selectedMuscles = selectedMuscles.includes(id)
			? selectedMuscles.filter((m) => m !== id)
			: [...selectedMuscles, id];
	}

	async function submitExercise(e: SubmitEvent) {
		e.preventDefault();
		if (!newName.trim()) return;
		saving = true;
		try {
			const payload = { name: newName.trim(), category: newCategory, primary_muscles: selectedMuscles };
			if (editingId != null) {
				await trainingApi.updateExercise(editingId, payload);
			} else {
				await trainingApi.createExercise(payload);
			}
			cancelForm();
			await load();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	async function remove(ex: Exercise) {
		if (!confirm(`Delete "${ex.name}"?`)) return;
		try {
			await trainingApi.deleteExercise(ex.id);
			await load();
		} catch (err) {
			error = apiErrorMessage(err);
		}
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Exercise library</h1>
	<Button onclick={() => (showForm ? cancelForm() : startNew())}>{showForm ? 'Cancel' : 'New exercise'}</Button>
</div>

{#if showForm}
	<form class="mt-4 flex flex-col gap-3 rounded-lg border border-neutral-800 p-4" onsubmit={submitExercise}>
		<Input placeholder="Exercise name" required bind:value={newName} />
		<select
			bind:value={newCategory}
			class="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
		>
			{#each categories as c (c)}
				<option value={c}>{c}</option>
			{/each}
		</select>
		<div>
			<p class="mb-1 text-xs text-neutral-500">Primary muscles (so it counts toward weekly volume)</p>
			<div class="flex flex-wrap gap-1.5">
				{#each muscles as mu (mu.id)}
					<button
						type="button"
						class="rounded-full border px-2.5 py-0.5 text-xs {selectedMuscles.includes(mu.id)
							? 'border-indigo-500 bg-indigo-950 text-indigo-200'
							: 'border-neutral-700 text-neutral-400 hover:border-neutral-500'}"
						onclick={() => toggleMuscle(mu.id)}
					>
						{mu.name}
					</button>
				{/each}
			</div>
		</div>
		<Button type="submit" disabled={saving}>
			{saving ? 'Saving…' : editingId != null ? 'Save changes' : 'Create custom exercise'}
		</Button>
	</form>
{/if}

<div class="mt-4">
	<input
		placeholder="Search exercises…"
		bind:value={query}
		oninput={onSearch}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-indigo-500"
	/>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<p class="mt-4 text-xs text-neutral-500">{exercises.length} exercise(s)</p>
	<ul class="mt-2 divide-y divide-neutral-800">
		{#each exercises as ex (ex.id)}
			<li class="flex items-center justify-between gap-2 py-3">
				<div>
					<span class="font-medium">{ex.name}</span>
					{#if !ex.is_global}
						<span class="ml-2 rounded bg-indigo-900 px-1.5 py-0.5 text-xs text-indigo-300">Custom</span>
					{/if}
					<div class="text-xs text-neutral-500">
						{ex.category}{ex.primary_muscle_names.length
							? ' · ' + ex.primary_muscle_names.join(', ')
							: ''}
					</div>
				</div>
				<div class="flex shrink-0 items-center gap-3 text-xs">
					<button class="text-orange-400 hover:text-orange-300" onclick={() => startEdit(ex)}>Edit</button>
					<button class="text-red-400 hover:text-red-300" onclick={() => remove(ex)}>Delete</button>
				</div>
			</li>
		{/each}
	</ul>
{/if}
