<script lang="ts">
	import { protocolsApi, type BloodMarker, type ParsedRow } from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	let {
		open = $bindable(false),
		markers,
		onsaved
	}: { open?: boolean; markers: BloodMarker[]; onsaved?: () => void } = $props();

	interface Row extends ParsedRow {
		include: boolean;
	}

	let rows = $state<Row[]>([]);
	let measuredOn = $state(new Date().toISOString().slice(0, 10));
	let parsing = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let fileName = $state('');

	async function onFile(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		fileName = file.name;
		parsing = true;
		error = null;
		rows = [];
		try {
			const report = await protocolsApi.parsePdf(file);
			if (report.measured_on) measuredOn = report.measured_on;
			rows = report.rows.map((r) => ({ ...r, include: r.matched }));
			if (rows.length === 0) error = 'No results could be read from this PDF.';
		} catch (err) {
			error = (err as Error).message;
		} finally {
			parsing = false;
			input.value = '';
		}
	}

	function flagFor(r: Row): string {
		const v = num(r.value);
		if (r.ref_high != null && r.ref_high !== '' && v > num(r.ref_high)) return 'high';
		if (r.ref_low != null && r.ref_low !== '' && v < num(r.ref_low)) return 'low';
		return 'in_range';
	}
	function flagClass(f: string): string {
		return f === 'high' ? 'text-red-300' : f === 'low' ? 'text-amber-300' : 'text-neutral-100';
	}
	function rangeText(r: Row): string {
		if (r.ref_low != null && r.ref_high != null) return `${r.ref_low}–${r.ref_high}`;
		if (r.ref_high != null) return `< ${r.ref_high}`;
		if (r.ref_low != null) return `> ${r.ref_low}`;
		return '—';
	}

	const selectable = $derived(rows.filter((r) => r.include && r.marker != null && r.value !== ''));

	async function save() {
		saving = true;
		error = null;
		try {
			const payload = selectable.map((r) => ({
				marker: r.marker as number,
				value: String(num(r.value)),
				unit: r.unit,
				ref_low: r.ref_low,
				ref_high: r.ref_high,
				source: 'pdf'
			}));
			await protocolsApi.bulkBloodResults(measuredOn, payload);
			open = false;
			rows = [];
			fileName = '';
			onsaved?.();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title="Import bloodwork from PDF" size="lg">
	<p class="text-xs text-neutral-500">
		Upload a lab PDF — values are extracted for you to review. Nothing is saved until you confirm, and
		the file itself isn't stored. Best-effort transcription, not medical advice; check the values.
	</p>

	<label
		class="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-md border border-neutral-700 px-3 py-2 text-sm text-neutral-200 hover:border-neutral-500"
	>
		<input type="file" accept="application/pdf" class="hidden" onchange={onFile} />
		{fileName ? 'Choose a different PDF' : 'Choose PDF…'}
	</label>
	{#if fileName}<span class="ml-2 text-xs text-neutral-500">{fileName}</span>{/if}

	{#if parsing}<p class="mt-3 text-sm text-neutral-400">Reading PDF…</p>{/if}
	{#if error}<p class="mt-3 text-sm text-red-400">{error}</p>{/if}

	{#if rows.length > 0}
		<label class="mt-4 flex flex-col text-xs text-neutral-500">
			Measurement date
			<input
				type="date"
				bind:value={measuredOn}
				class="mt-1 w-44 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			/>
		</label>

		<div class="mt-3 max-h-[50vh] overflow-auto">
			<table class="w-full border-collapse text-sm">
				<thead class="sticky top-0 bg-neutral-950 text-xs text-neutral-500">
					<tr>
						<th class="px-2 py-1 text-left font-normal">Use</th>
						<th class="px-2 py-1 text-left font-normal">Marker</th>
						<th class="px-2 py-1 text-right font-normal">Value</th>
						<th class="px-2 py-1 text-left font-normal">Unit</th>
						<th class="px-2 py-1 text-right font-normal">Range</th>
					</tr>
				</thead>
				<tbody>
					{#each rows as r, i (i)}
						<tr class="border-t border-neutral-800 {r.marker == null ? 'opacity-60' : ''}">
							<td class="px-2 py-1"><input type="checkbox" bind:checked={r.include} /></td>
							<td class="px-2 py-1">
								<select
									bind:value={r.marker}
									class="w-48 rounded border border-neutral-700 bg-neutral-900 px-1.5 py-1 text-sm text-neutral-100"
								>
									<option value={null}>— skip ({r.raw_name}) —</option>
									{#each markers as m (m.id)}<option value={m.id}>{m.name}</option>{/each}
								</select>
							</td>
							<td class="px-2 py-1 text-right">
								<input
									bind:value={r.value}
									inputmode="decimal"
									class="w-20 rounded border border-neutral-700 bg-neutral-900 px-1.5 py-1 text-right text-sm {flagClass(
										flagFor(r)
									)}"
								/>
							</td>
							<td class="px-2 py-1 text-neutral-400">{r.unit}</td>
							<td class="px-2 py-1 text-right text-neutral-500">{rangeText(r)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mt-4 flex flex-wrap items-center gap-3">
			<div class="w-48">
				<Button type="button" onclick={save} disabled={saving || selectable.length === 0}>
					{saving ? 'Saving…' : `Save ${selectable.length} result${selectable.length === 1 ? '' : 's'}`}
				</Button>
			</div>
			<span class="text-xs text-neutral-500">
				Out-of-range values are coloured. Unmatched rows default to “skip” — pick a marker to include
				them.
			</span>
		</div>
	{/if}
</Modal>
