<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { trainingApi, type Program } from '$lib/training/api';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Card from '$lib/components/ui/Card.svelte';

	let programs = $state<Program[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let newName = $state('');
	let creating = $state(false);

	async function load() {
		programs = await trainingApi.programs();
	}

	onMount(async () => {
		try {
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function create(e: SubmitEvent) {
		e.preventDefault();
		if (!newName.trim()) return;
		creating = true;
		try {
			const program = await trainingApi.createProgram({ name: newName.trim() });
			await goto(`/training/programs/${program.id}`);
		} catch (err) {
			error = (err as Error).message;
		} finally {
			creating = false;
		}
	}

	async function activate(id: number) {
		await trainingApi.activateProgram(id);
		await load();
	}

	async function remove(id: number) {
		if (!confirm('Delete this program?')) return;
		await trainingApi.deleteProgram(id);
		await load();
	}
</script>

<h1 class="text-xl font-semibold">Programs</h1>

<form class="mt-4 flex gap-2" onsubmit={create}>
	<Input placeholder="New program name (e.g. Push/Pull/Legs)" bind:value={newName} />
	<div class="w-40 shrink-0">
		<Button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create'}</Button>
	</div>
</form>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if programs.length === 0}
	<p class="mt-6 text-neutral-500">No programs yet — create your first above.</p>
{:else}
	<div class="mt-6 space-y-3">
		{#each programs as program (program.id)}
			<Card>
				<div class="flex items-center justify-between">
					<a class="font-medium hover:text-indigo-300" href={`/training/programs/${program.id}`}>
						{program.name}
					</a>
					<div class="flex items-center gap-3 text-sm">
						{#if program.is_active}
							<span class="rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
						{:else}
							<button class="text-neutral-400 hover:text-white" onclick={() => activate(program.id)}>
								Set active
							</button>
						{/if}
						<button class="text-red-400 hover:text-red-300" onclick={() => remove(program.id)}>
							Delete
						</button>
					</div>
				</div>
				<p class="mt-1 text-xs text-neutral-500">{program.days.length} day(s)</p>
			</Card>
		{/each}
	</div>
{/if}
