<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		type MatrixCell,
		type MatrixRow,
		type PhaseDoseMatrix
	} from '$lib/protocols/api';
	import { coachingApi, type Phase } from '$lib/coaching/api';

	let phases = $state<Phase[]>([]);
	let activeProtocolId = $state<number | null>(null);
	let selectedPhase = $state<number | null>(null);
	let matrix = $state<PhaseDoseMatrix | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	async function loadMatrix() {
		if (activeProtocolId == null) return;
		matrix = await protocolsApi.phaseMatrix(activeProtocolId, selectedPhase ?? undefined);
		if (selectedPhase == null && matrix) selectedPhase = matrix.phase.id; // sync the picker
	}

	onMount(async () => {
		try {
			const [protocols, ph] = await Promise.all([
				protocolsApi.protocols(),
				coachingApi.phases()
			]);
			phases = ph;
			const active = protocols.find((p) => p.is_active) ?? protocols[0];
			activeProtocolId = active?.id ?? null;
			if (activeProtocolId == null) {
				error = 'No protocol yet — create one under Manage first.';
			} else if (phases.length === 0) {
				error = 'No phase yet — create a phase (with a start + finish date) to see its dose table.';
			} else {
				await loadMatrix();
			}
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function onPhaseChange() {
		loading = true;
		error = null;
		try {
			await loadMatrix();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	const num = (s: string | null) => (s ? Number(s) : 0);

	// State → cell colour. Skipped is struck-through so a sick-week is obvious.
	const STATE_CLASS: Record<string, string> = {
		done: 'bg-green-950/60 text-green-300',
		partial: 'bg-amber-950/50 text-amber-300',
		skipped: 'bg-red-950/50 text-red-300',
		planned: 'text-neutral-400',
		none: 'text-neutral-700'
	};

	// Main dose number for a cell — always the plan in force *that* week, so the table
	// reflects the true history across adjustments (not the currently-active protocol).
	// Weekly = summed dose (taken for logged weeks, else planned); daily = per-day dose.
	function mainDose(row: MatrixRow, cell: MatrixCell): string {
		if (row.mode === 'weekly') {
			if (cell.state === 'planned') return cell.planned_amount ? `${Math.round(num(cell.planned_amount))} ${row.unit}` : '—';
			if (cell.taken_count || cell.skipped_count) return `${Math.round(num(cell.taken_amount))} ${row.unit}`;
			return cell.planned_amount ? `${Math.round(num(cell.planned_amount))} ${row.unit}` : '—';
		}
		return cell.daily_amount ? `${Math.round(num(cell.daily_amount))} ${row.unit}/d` : '—';
	}

	// Weeks where the in-force protocol changes vs. the previous week — drawn with a
	// divider + label so an adjustment is obvious at a glance.
	const adjustmentWeeks = $derived.by(() => {
		const out = new Set<number>();
		const ws = matrix?.weeks ?? [];
		for (let i = 1; i < ws.length; i++)
			if (ws[i].protocol !== ws[i - 1].protocol) out.add(ws[i].index);
		return out;
	});

	function badge(cell: MatrixCell): string {
		const parts: string[] = [];
		if (cell.taken_count) parts.push(`✓${cell.taken_count}`);
		if (cell.skipped_count) parts.push(`⊘${cell.skipped_count}`);
		if (!cell.taken_count && !cell.skipped_count && cell.scheduled) parts.push(`·${cell.scheduled}`);
		return parts.join(' ');
	}

	const fmt = (iso: string) =>
		new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

	// Split rows into per-class sections (Injectable/Oral steroids, Peptides, …).
	const GROUP_ORDER = [
		'Injectable steroids', 'Oral steroids', 'SARMs', 'Peptides', 'Ancillaries', 'Supplements', 'Other'
	];
	const groupedRows = $derived.by(() => {
		const by = new Map<string, MatrixRow[]>();
		for (const r of matrix?.rows ?? []) by.set(r.group, [...(by.get(r.group) ?? []), r]);
		return [...by.entries()].sort((a, b) => GROUP_ORDER.indexOf(a[0]) - GROUP_ORDER.indexOf(b[0]));
	});
</script>

<div class="flex items-center justify-between">
	<div>
		<a class="text-sm text-neutral-400 hover:text-white" href="/protocols">← Protocols</a>
		<h1 class="text-xl font-semibold">Dose table</h1>
	</div>
	{#if phases.length > 0}
		<select
			bind:value={selectedPhase}
			onchange={onPhaseChange}
			class="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
		>
			{#each phases as p (p.id)}
				<option value={p.id}>{p.name}</option>
			{/each}
		</select>
	{/if}
</div>

<p class="mt-2 text-xs text-neutral-500">
	Weekly plan vs. what you logged. Injectable anabolics are summed to a <strong>weekly</strong> dose;
	everything else lists its <strong>daily</strong> dose. Past/current weeks reflect your logs
	(<span class="text-green-400">taken ✓</span>, <span class="text-red-400">skipped ⊘</span>); future
	weeks show the plan in force that week. It spans the whole phase across protocol changes —
	a dropped compound keeps its logged weeks (then blank), and a newly-added one appears from its week.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-sm text-amber-400">{error}</p>
{:else if matrix}
	{#if matrix.rows.length === 0}
		<p class="mt-6 text-sm text-neutral-500">Nothing planned or logged in this phase yet.</p>
	{:else}
		<div class="mt-4 overflow-x-auto">
			<table class="min-w-full border-separate border-spacing-0 text-sm">
				<thead>
					<tr class="text-xs text-neutral-500">
						<th class="sticky left-0 z-10 bg-neutral-950 px-2 py-2 text-left font-medium">Item</th>
						{#each matrix.weeks as w (w.index)}
							<th class="px-2 py-2 text-center font-medium whitespace-nowrap {adjustmentWeeks.has(w.index) ? 'border-l-2 border-orange-500/60' : ''}">
								<div>Wk {w.index + 1}</div>
								<div class="text-[10px] font-normal text-neutral-600">{fmt(w.start)}</div>
								{#if (w.index === 0 || adjustmentWeeks.has(w.index)) && w.protocol}
									<div class="text-[9px] font-medium text-orange-400">
										{adjustmentWeeks.has(w.index) ? '→ ' : ''}{w.protocol}
									</div>
								{/if}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each groupedRows as [group, rows] (group)}
						<tr>
							<td colspan={matrix.weeks.length + 1} class="sticky left-0 bg-neutral-950 px-2 pt-4 pb-1 text-left text-xs font-semibold uppercase tracking-wide text-neutral-400">{group}</td>
						</tr>
						{#each rows as row (row.item_id)}
						<tr class="border-t border-neutral-800">
							<td class="sticky left-0 z-10 bg-neutral-950 px-2 py-2 align-top">
								<div class="font-medium">{row.name}</div>
								<div class="text-[10px] text-neutral-500">
									{row.mode === 'weekly' ? 'weekly' : 'daily'}
									{#if row.kind === 'compound' && row.mode === 'weekly'}💉{/if}
								</div>
							</td>
							{#each row.cells as cell (cell.week)}
								<td class="px-1 py-1 text-center {adjustmentWeeks.has(cell.week) ? 'border-l-2 border-orange-500/30' : ''}">
									<div class="rounded px-1.5 py-1 {STATE_CLASS[cell.state]}">
										<div class="whitespace-nowrap {cell.state === 'skipped' && !cell.taken_count ? 'line-through' : ''}">
											{mainDose(row, cell)}
										</div>
										{#if badge(cell)}
											<div class="text-[10px] opacity-80">{badge(cell)}</div>
										{/if}
									</div>
								</td>
							{/each}
						</tr>
						{/each}
					{/each}
				</tbody>
			</table>
		</div>
		<p class="mt-3 text-xs text-neutral-600">
			Legend: ✓ taken · ⊘ skipped · ·N scheduled this week · <span class="text-orange-400">orange divider</span> = protocol adjusted (new plan from that week).
		</p>
	{/if}
{/if}
