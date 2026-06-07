<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type Supplement } from '$lib/protocols/api';
	import { nutritionApi, type Nutrient } from '$lib/nutrition/api';
	import { num } from '$lib/protocols/calc';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	// Create OR edit a custom supplement (+ its per-serving nutrients) in-context.
	// Pass `edit` to load an existing supplement. Nutrient rows can be added AND
	// removed.
	let {
		open = $bindable(false),
		oncreated,
		onupdated,
		onclose,
		edit = null
	}: {
		open?: boolean;
		oncreated?: (s: Supplement) => void;
		onupdated?: (s: Supplement) => void;
		onclose?: () => void;
		edit?: Supplement | null;
	} = $props();

	let nutrients = $state<Nutrient[]>([]);
	let name = $state('');
	let brand = $state('');
	let benefit = $state('');
	let rows = $state<{ nutrient: number | null; amount: string }[]>([{ nutrient: null, amount: '' }]);
	let saving = $state(false);
	let error = $state<string | null>(null);

	onMount(async () => {
		nutrients = await nutritionApi.nutrients().catch(() => []);
	});

	function reset() {
		name = brand = benefit = '';
		rows = [{ nutrient: null, amount: '' }];
	}

	// Load the supplement being edited when the modal opens (once per open).
	let lastEdit: Supplement | null = null;
	$effect(() => {
		if (open && edit && edit !== lastEdit) {
			lastEdit = edit;
			name = edit.name;
			brand = edit.brand ?? '';
			benefit = edit.target_benefit ?? '';
			rows = edit.supplement_nutrients.length
				? edit.supplement_nutrients.map((n) => ({
						nutrient: n.nutrient,
						amount: String(num(n.amount_per_serving))
					}))
				: [{ nutrient: null, amount: '' }];
		}
		if (!open) lastEdit = null;
	});

	function addRow() {
		rows = [...rows, { nutrient: null, amount: '' }];
	}
	function removeRow(i: number) {
		rows = rows.filter((_, idx) => idx !== i);
		if (rows.length === 0) addRow();
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		try {
			const supplement_nutrients = rows
				.filter((r) => r.nutrient != null && r.amount !== '')
				.map((r) => ({ nutrient: r.nutrient as number, amount_per_serving: String(num(r.amount)) }));
			const data = {
				name: name.trim(),
				brand: brand.trim(),
				target_benefit: benefit.trim(),
				supplement_nutrients
			};
			if (edit) {
				onupdated?.(await protocolsApi.updateSupplement(edit.id, data));
			} else {
				oncreated?.(await protocolsApi.createSupplement(data));
			}
			reset();
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	const fieldClass =
		'rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100';
</script>

<Modal bind:open title={edit ? 'Edit supplement' : 'New supplement'} {onclose}>
	<form class="space-y-3" onsubmit={submit}>
		<div class="flex gap-2">
			<Input placeholder="Name (e.g. Vitamin D3)" required bind:value={name} />
			<Input placeholder="Brand (optional)" bind:value={brand} />
		</div>
		<Input placeholder="Target benefit (optional)" bind:value={benefit} />
		<p class="text-xs text-neutral-500">Nutrients per serving:</p>
		{#each rows as row, i (i)}
			<div class="flex items-center gap-2">
				<select bind:value={row.nutrient} class="flex-[2] {fieldClass}">
					<option value={null}>Choose nutrient…</option>
					{#each nutrients as n (n.id)}
						<option value={n.id}>{n.name} ({n.unit})</option>
					{/each}
				</select>
				<input type="number" step="0.001" placeholder="amount" bind:value={row.amount} class="flex-1 {fieldClass}" />
				<button
					type="button"
					class="shrink-0 px-1 text-neutral-600 hover:text-red-400"
					aria-label="Remove nutrient"
					onclick={() => removeRow(i)}
				>
					✕
				</button>
			</div>
		{/each}
		<button type="button" class="text-xs text-indigo-400 hover:text-indigo-300" onclick={addRow}>
			+ Add another nutrient
		</button>
		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		<Button type="submit" disabled={saving}>
			{saving ? 'Saving…' : edit ? 'Save changes' : 'Create supplement'}
		</Button>
	</form>
</Modal>
