<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { protocolsApi, type Protocol } from '$lib/protocols/api';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Card from '$lib/components/ui/Card.svelte';

	let protocols = $state<Protocol[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let newName = $state('');
	let creating = $state(false);

	async function load() {
		protocols = await protocolsApi.protocols();
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
			const p = await protocolsApi.createProtocol({ name: newName.trim() });
			await goto(`/protocols/manage/${p.id}`);
		} catch (err) {
			error = (err as Error).message;
		} finally {
			creating = false;
		}
	}

	async function activate(id: number) {
		await protocolsApi.activateProtocol(id);
		await load();
	}

	async function remove(id: number) {
		if (!confirm('Delete this protocol?')) return;
		await protocolsApi.deleteProtocol(id);
		await load();
	}
</script>

<h1 class="text-xl font-semibold">Manage protocols</h1>

<form class="mt-4 flex gap-2" onsubmit={create}>
	<Input placeholder="New protocol name (e.g. TRT, Summer cycle)" bind:value={newName} />
	<div class="w-40 shrink-0"><Button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create'}</Button></div>
</form>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if protocols.length === 0}
	<p class="mt-6 text-neutral-500">No protocols yet — create your first above.</p>
{:else}
	<div class="mt-6 space-y-3">
		{#each protocols as p (p.id)}
			<Card>
				<div class="flex items-center justify-between">
					<a class="font-medium hover:text-indigo-300" href={`/protocols/manage/${p.id}`}>{p.name}</a>
					<div class="flex items-center gap-3 text-sm">
						{#if p.is_active}
							<span class="rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
						{:else}
							<button class="text-neutral-400 hover:text-white" onclick={() => activate(p.id)}>Set active</button>
						{/if}
						<button class="text-red-400 hover:text-red-300" onclick={() => remove(p.id)}>Delete</button>
					</div>
				</div>
				<p class="mt-1 text-xs text-neutral-500">{p.items.length} item(s)</p>
			</Card>
		{/each}
	</div>
{/if}
