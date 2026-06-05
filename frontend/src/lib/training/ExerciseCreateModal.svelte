<script lang="ts">
	import { trainingApi, type Exercise } from '$lib/training/api';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	// Create a custom exercise without leaving the current page. Mount it always
	// and toggle `open`; on success the new exercise is handed back via `oncreated`
	// so the caller can select it.
	let {
		open = $bindable(false),
		oncreated,
		onclose
	}: {
		open?: boolean;
		oncreated: (ex: Exercise) => void;
		onclose?: () => void;
	} = $props();

	const categories = [
		'barbell', 'dumbbell', 'machine', 'cable', 'bodyweight', 'smith', 'kettlebell', 'banded', 'other'
	];

	let name = $state('');
	let category = $state('barbell');
	let saving = $state(false);
	let error = $state<string | null>(null);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		try {
			const ex = await trainingApi.createExercise({ name: name.trim(), category });
			oncreated(ex);
			name = '';
			category = 'barbell';
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title="New exercise" size="sm" {onclose}>
	<form class="space-y-3" onsubmit={submit}>
		<Input placeholder="Exercise name" required bind:value={name} />
		<select
			bind:value={category}
			class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
		>
			{#each categories as c (c)}
				<option value={c}>{c}</option>
			{/each}
		</select>
		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		<Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create custom exercise'}</Button>
	</form>
</Modal>
