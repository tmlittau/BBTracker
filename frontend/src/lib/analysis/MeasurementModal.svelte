<script lang="ts">
	import { analysisApi, BODY_FAT_METHODS, MEASUREMENT_TYPES } from '$lib/analysis/api';
	import { isoDate } from '$lib/date';
	import Modal from '$lib/components/ui/Modal.svelte';

	let { open = $bindable(false), onsaved }: { open?: boolean; onsaved?: () => void } = $props();

	let mType = $state('waist');
	let mValue = $state('');
	let mMethod = $state('dexa');
	let mDate = $state(isoDate());
	let saving = $state(false);
	let error = $state<string | null>(null);
	const isBodyFat = $derived(mType === 'body_fat');
	const unitFor = (t: string) => MEASUREMENT_TYPES.find((m) => m.key === t)?.unit ?? '';

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (mValue === '') return;
		saving = true;
		error = null;
		try {
			await analysisApi.addMeasurement({
				date: mDate,
				type: mType,
				value: String(Number(mValue)),
				method: isBodyFat ? mMethod : undefined
			});
			mValue = '';
			onsaved?.();
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	const fieldClass =
		'mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100';
</script>

<Modal bind:open title="Add measurement" size="sm">
	<form class="space-y-3" onsubmit={save}>
		<label class="flex flex-col text-xs text-neutral-500"
			>Measurement
			<select bind:value={mType} class={fieldClass}>
				{#each MEASUREMENT_TYPES as t (t.key)}<option value={t.key}>{t.label}</option>{/each}
			</select>
		</label>
		<label class="flex flex-col text-xs text-neutral-500"
			>Value ({unitFor(mType)})
			<input type="number" step="0.1" inputmode="decimal" bind:value={mValue} class={fieldClass} />
		</label>
		{#if isBodyFat}
			<label class="flex flex-col text-xs text-neutral-500"
				>Method
				<select bind:value={mMethod} class={fieldClass}>
					{#each BODY_FAT_METHODS as m (m.key)}<option value={m.key}>{m.label}</option>{/each}
				</select>
			</label>
		{/if}
		<label class="flex flex-col text-xs text-neutral-500"
			>Date
			<input type="date" bind:value={mDate} class={fieldClass} />
		</label>
		{#if error}<p class="text-xs text-red-400">{error}</p>{/if}
		<div class="flex justify-end gap-2 pt-1">
			<button
				type="button"
				class="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
				onclick={() => (open = false)}>Cancel</button
			>
			<button
				type="submit"
				disabled={saving}
				class="rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50"
				>{saving ? 'Saving…' : 'Add'}</button
			>
		</div>
	</form>
</Modal>
