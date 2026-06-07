<script lang="ts">
	import { protocolsApi, ROUTES, type Compound } from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	// Create OR edit a custom compound (owner-scoped) in-context. Pass `edit` to
	// load an existing compound into the form. half_life_hours + active_fraction
	// are factual reference constants for concentration modelling.
	let {
		open = $bindable(false),
		oncreated,
		onupdated,
		onclose,
		edit = null
	}: {
		open?: boolean;
		oncreated?: (c: Compound) => void;
		onupdated?: (c: Compound) => void;
		onclose?: () => void;
		edit?: Compound | null;
	} = $props();

	const CLASSES = [
		{ key: 'anabolic', label: 'Anabolic steroid' },
		{ key: 'peptide', label: 'Peptide' },
		{ key: 'sarm', label: 'SARM' },
		{ key: 'ancillary', label: 'Ancillary / pharmaceutical' },
		{ key: 'other', label: 'Other' }
	];
	const UNITS = ['mg', 'mcg', 'iu', 'ml', 'tablet', 'capsule'];

	let name = $state('');
	let compoundClass = $state('anabolic');
	let unit = $state('mg');
	let route = $state('im');
	let halfLife = $state('');
	let ester = $state('');
	let activeFraction = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	const selectClass =
		'w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100';

	function reset() {
		name = ester = halfLife = activeFraction = '';
		compoundClass = 'anabolic';
		unit = 'mg';
		route = 'im';
	}

	// Load the compound being edited when the modal opens (once per open).
	let lastEdit: Compound | null = null;
	$effect(() => {
		if (open && edit && edit !== lastEdit) {
			lastEdit = edit;
			name = edit.name;
			compoundClass = edit.compound_class;
			unit = edit.default_unit;
			route = edit.default_route;
			halfLife = edit.half_life_hours ?? '';
			ester = edit.ester ?? '';
			activeFraction = edit.active_fraction ?? '';
		}
		if (!open) lastEdit = null;
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		try {
			const data = {
				name: name.trim(),
				compound_class: compoundClass,
				default_unit: unit,
				default_route: route,
				half_life_hours: halfLife === '' ? null : String(num(halfLife)),
				ester: ester.trim(),
				active_fraction: activeFraction === '' ? '1.000' : String(num(activeFraction))
			};
			if (edit) {
				onupdated?.(await protocolsApi.updateCompound(edit.id, data));
			} else {
				oncreated?.(await protocolsApi.createCompound(data));
			}
			reset();
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title={edit ? 'Edit compound' : 'New compound'} {onclose}>
	<form class="space-y-3" onsubmit={submit}>
		<Input placeholder="Name (e.g. Testosterone Enanthate)" required bind:value={name} />
		<div class="grid grid-cols-2 gap-2">
			<label class="flex flex-col text-xs text-neutral-500">
				Class
				<select bind:value={compoundClass} class="mt-1 {selectClass}">
					{#each CLASSES as c (c.key)}<option value={c.key}>{c.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Default route
				<select bind:value={route} class="mt-1 {selectClass}">
					{#each ROUTES as r (r.key)}<option value={r.key}>{r.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Default unit
				<select bind:value={unit} class="mt-1 {selectClass}">
					{#each UNITS as u (u)}<option value={u}>{u}</option>{/each}
				</select>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Ester (optional)
				<input
					bind:value={ester}
					placeholder="e.g. Enanthate"
					class="mt-1 {selectClass}"
				/>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Half-life (hours)
				<input
					type="number"
					step="0.01"
					bind:value={halfLife}
					placeholder="optional"
					class="mt-1 {selectClass}"
				/>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Active fraction (≤1)
				<input
					type="number"
					step="0.001"
					min="0"
					max="1"
					bind:value={activeFraction}
					placeholder="1.000"
					class="mt-1 {selectClass}"
				/>
			</label>
		</div>
		<p class="text-xs text-neutral-600">
			Half-life + active fraction are optional factual constants used only to visualise your own
			logged doses — not dosing guidance.
		</p>
		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		<Button type="submit" disabled={saving}>
			{saving ? 'Saving…' : edit ? 'Save changes' : 'Create compound'}
		</Button>
	</form>
</Modal>
