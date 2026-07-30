<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		clientPlan,
		writeError,
		DOSE_UNITS,
		ROUTES,
		FREQUENCIES,
		TIMES_OF_DAY,
		WEEKDAYS,
		type ClientPlan,
		type ProtocolBrief,
		type Protocol,
		type ProtocolItem,
		type CompoundRef,
		type SupplementRef
	} from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let {
		clientId,
		plan: planProp,
		canEdit: canEditProp,
		onApply
	}: {
		clientId?: number;
		plan?: ClientPlan;
		canEdit?: boolean;
		onApply?: (id: number, name: string) => void;
	} = $props();
	const plan = $derived(planProp ?? clientPlan(clientId!));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(canEditProp ?? ctx?.canEdit ?? false);
	const isTemplate = $derived(onApply != null);

	let protocols = $state<ProtocolBrief[]>([]);
	let selectedId = $state<number | null>(null);
	let protocol = $state<Protocol | null>(null);
	let loading = $state(true);
	let loadingDetail = $state(false);
	let error = $state<string | null>(null);
	let newName = $state('');
	let busy = $state(false);

	// The backend requires every item to link exactly one compound or supplement
	// (item_name is derived from it server-side), so there is no free-text "custom" item.
	type Kind = 'compound' | 'supplement';
	interface ItemDraft {
		kind: Kind;
		compound: number | null;
		supplement: number | null;
		item_name: string; // display only — reflects the picked library entry
		dose_amount: string;
		dose_unit: string;
		route: string;
		frequency: string;
		days_of_week: number[];
		times_of_day: string[];
		target_benefit: string;
		notes: string;
	}
	const emptyDraft = (): ItemDraft => ({
		kind: 'compound',
		compound: null,
		supplement: null,
		item_name: '',
		dose_amount: '',
		dose_unit: 'mg',
		route: 'im',
		frequency: 'weekly',
		days_of_week: [],
		times_of_day: [],
		target_benefit: '',
		notes: ''
	});

	// editor state — at most one open (add form OR one item being edited)
	let adding = $state(false);
	let editingId = $state<number | null>(null);
	let draft = $state<ItemDraft>(emptyDraft());

	// library picker
	let libQuery = $state('');
	let libResults = $state<{ id: number; name: string; sub: string; unit: string; route: string }[]>([]);
	let libLoading = $state(false);
	let libTimer: ReturnType<typeof setTimeout> | undefined;

	async function loadList(select?: number) {
		loading = true;
		error = null;
		try {
			protocols = await plan.protocols();
			const pick = select ?? selectedId ?? protocols.find((p) => p.is_active)?.id ?? protocols[0]?.id ?? null;
			if (pick != null) await selectProtocol(pick);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function selectProtocol(id: number) {
		selectedId = id;
		adding = false;
		editingId = null;
		loadingDetail = true;
		try {
			protocol = await plan.protocol(id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loadingDetail = false;
		}
	}

	onMount(() => loadList());

	async function createProtocol() {
		if (!newName.trim()) return;
		busy = true;
		error = null;
		try {
			const p = await plan.createProtocol({ name: newName.trim() });
			newName = '';
			await loadList(p.id);
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function activate() {
		if (!protocol) return;
		try {
			await plan.activateProtocol(protocol.id);
			await loadList(protocol.id);
		} catch (e) {
			error = writeError(e);
		}
	}

	async function removeProtocol() {
		if (!protocol || !confirm(`Delete protocol “${protocol.name}” and all its items?`)) return;
		try {
			await plan.deleteProtocol(protocol.id);
			selectedId = null;
			protocol = null;
			await loadList();
		} catch (e) {
			error = writeError(e);
		}
	}

	// --- item editor ---
	function resetPicker() {
		libQuery = '';
		libResults = [];
	}
	function openAdd() {
		editingId = null;
		draft = emptyDraft();
		resetPicker();
		adding = true;
		searchLibrary();
	}
	function openEdit(item: ProtocolItem) {
		adding = false;
		editingId = item.id;
		draft = {
			kind: item.supplement ? 'supplement' : 'compound',
			compound: item.compound,
			supplement: item.supplement,
			item_name: item.item_name,
			dose_amount: item.dose_amount ?? '',
			dose_unit: item.dose_unit || 'mg',
			route: item.route || '',
			frequency: item.frequency,
			days_of_week: [...(item.days_of_week ?? [])],
			times_of_day: [...(item.times_of_day ?? [])],
			target_benefit: item.target_benefit,
			notes: item.notes
		};
		resetPicker();
	}
	function cancelEditor() {
		adding = false;
		editingId = null;
	}

	function setKind(k: Kind) {
		draft.kind = k;
		draft.compound = null;
		draft.supplement = null;
		draft.item_name = '';
		if (k === 'supplement') draft.route = '';
		resetPicker();
		searchLibrary();
	}
	function onLibInput() {
		clearTimeout(libTimer);
		libTimer = setTimeout(searchLibrary, 250);
	}
	async function searchLibrary() {
		libLoading = true;
		try {
			if (draft.kind === 'compound') {
				const rows = await plan.compounds(libQuery);
				libResults = rows.slice(0, 25).map((c: CompoundRef) => ({
					id: c.id,
					name: c.name,
					sub: c.compound_class,
					unit: c.default_unit,
					route: c.default_route
				}));
			} else {
				const rows = await plan.supplements(libQuery);
				libResults = rows.slice(0, 25).map((s: SupplementRef) => ({
					id: s.id,
					name: s.name,
					sub: s.brand || s.serving_label,
					unit: 'serving',
					route: ''
				}));
			}
		} catch (e) {
			error = (e as Error).message;
		} finally {
			libLoading = false;
		}
	}
	function pickLib(r: { id: number; name: string; unit: string; route: string }) {
		if (draft.kind === 'compound') {
			draft.compound = r.id;
			draft.supplement = null;
		} else {
			draft.supplement = r.id;
			draft.compound = null;
		}
		draft.item_name = r.name;
		if (r.unit) draft.dose_unit = r.unit;
		draft.route = r.route;
	}
	function toggle<T>(arr: T[], v: T): T[] {
		return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
	}

	function draftPayload(): Partial<ProtocolItem> {
		// item_name is derived server-side from the compound/supplement — don't send it.
		return {
			compound: draft.kind === 'compound' ? draft.compound : null,
			supplement: draft.kind === 'supplement' ? draft.supplement : null,
			dose_amount: draft.dose_amount.trim() || null,
			dose_unit: draft.dose_unit,
			route: draft.route,
			frequency: draft.frequency,
			days_of_week: draft.frequency === 'specific_days' ? draft.days_of_week : [],
			times_of_day: draft.times_of_day,
			target_benefit: draft.target_benefit.trim(),
			notes: draft.notes.trim()
		};
	}
	const draftValid = $derived(
		(draft.kind === 'compound' && draft.compound != null) ||
			(draft.kind === 'supplement' && draft.supplement != null)
	);

	async function saveItem() {
		if (!protocol || !draftValid) return;
		busy = true;
		error = null;
		try {
			if (editingId != null) {
				await plan.updateItem(editingId, draftPayload());
			} else {
				await plan.createItem({ protocol: protocol.id, order: protocol.items.length, ...draftPayload() });
			}
			cancelEditor();
			await selectProtocol(protocol.id);
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function removeItem(item: ProtocolItem) {
		if (!confirm(`Remove ${item.item_name}?`)) return;
		try {
			await plan.deleteItem(item.id);
			if (protocol) protocol.items = protocol.items.filter((i) => i.id !== item.id);
		} catch (e) {
			error = writeError(e);
		}
	}

	const freqLabel = (v: string) => FREQUENCIES.find((f) => f.value === v)?.label ?? v;
	function itemSummary(item: ProtocolItem): string {
		const parts: string[] = [];
		if (item.dose_amount) parts.push(`${item.dose_amount} ${item.dose_unit}`);
		const route = ROUTES.find((r) => r.value === item.route)?.label;
		if (route && item.route) parts.push(route);
		parts.push(freqLabel(item.frequency));
		if (item.frequency === 'specific_days' && item.days_of_week?.length) {
			parts.push(item.days_of_week.map((d) => WEEKDAYS.find((w) => w.value === d)?.label).join('/'));
		}
		if (item.times_of_day?.length) {
			parts.push(item.times_of_day.map((t) => TIMES_OF_DAY.find((x) => x.value === t)?.label ?? t).join('/'));
		}
		return parts.join(' · ');
	}
</script>

{#snippet editor()}
	<div class="mt-2 space-y-3 rounded-md border border-neutral-800 bg-neutral-950 p-3">
		<!-- kind -->
		<div class="flex gap-1 text-xs">
			{#each [['compound', 'Compound'], ['supplement', 'Supplement']] as [k, label] (k)}
				<button
					onclick={() => setKind(k as Kind)}
					class="rounded-full px-3 py-1 {draft.kind === k ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-300'}"
				>
					{label}
				</button>
			{/each}
		</div>

		<!-- library picker (compound/supplement) -->
		<div>
			<input
				placeholder={draft.kind === 'compound' ? 'Search compounds…' : 'Search supplements…'}
				bind:value={libQuery}
				oninput={onLibInput}
				class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			/>
			<div class="mt-1.5 max-h-40 space-y-0.5 overflow-y-auto">
				{#if libLoading}
					<p class="px-1 py-1.5 text-xs text-neutral-500">Searching…</p>
				{:else}
					{#each libResults as r (r.id)}
						{@const chosen = (draft.kind === 'compound' ? draft.compound : draft.supplement) === r.id}
						<button
							onclick={() => pickLib(r)}
							class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm {chosen ? 'bg-neutral-800 text-white' : 'text-neutral-200 hover:bg-neutral-800'}"
						>
							<span>{r.name}</span>
							<span class="ml-2 truncate text-[10px] text-neutral-500">{r.sub}</span>
						</button>
					{:else}
						<p class="px-1 py-1.5 text-xs text-neutral-500">No matches.</p>
					{/each}
				{/if}
			</div>
		</div>

		<!-- chosen item (item_name is derived from the library entry, server-side) -->
		<div class="rounded border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-sm">
			{#if draft.item_name}
				<span class="text-neutral-100">{draft.item_name}</span>
			{:else}
				<span class="text-neutral-500">Choose a {draft.kind} above…</span>
			{/if}
		</div>

		<!-- dose / unit / route -->
		<div class="grid grid-cols-3 gap-2">
			<label class="flex flex-col text-xs text-neutral-500">
				Dose
				<input type="text" inputmode="decimal" bind:value={draft.dose_amount} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Unit
				<select bind:value={draft.dose_unit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100">
					{#each DOSE_UNITS as u (u.value)}<option value={u.value}>{u.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Route
				<select bind:value={draft.route} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100">
					{#each ROUTES as r (r.value)}<option value={r.value}>{r.label}</option>{/each}
				</select>
			</label>
		</div>

		<!-- frequency -->
		<label class="block text-xs text-neutral-500">
			Frequency
			<select bind:value={draft.frequency} class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100">
				{#each FREQUENCIES as f (f.value)}<option value={f.value}>{f.label}</option>{/each}
			</select>
		</label>

		{#if draft.frequency === 'specific_days'}
			<div class="flex flex-wrap gap-1">
				{#each WEEKDAYS as d (d.value)}
					<button
						onclick={() => (draft.days_of_week = toggle(draft.days_of_week, d.value))}
						class="rounded-full px-2.5 py-1 text-xs {draft.days_of_week.includes(d.value) ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-400'}"
					>
						{d.label}
					</button>
				{/each}
			</div>
		{/if}

		<!-- times of day -->
		<div>
			<span class="text-xs text-neutral-500">Timing</span>
			<div class="mt-1 flex flex-wrap gap-1">
				{#each TIMES_OF_DAY as t (t.value)}
					<button
						onclick={() => (draft.times_of_day = toggle(draft.times_of_day, t.value))}
						class="rounded-full px-2.5 py-1 text-xs {draft.times_of_day.includes(t.value) ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-400'}"
					>
						{t.label}
					</button>
				{/each}
			</div>
		</div>

		<input
			bind:value={draft.target_benefit}
			placeholder="Target benefit (optional)"
			class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
		/>
		<textarea
			bind:value={draft.notes}
			rows="2"
			placeholder="Notes (optional)"
			class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
		></textarea>

		<div class="flex items-center gap-2">
			<button
				onclick={saveItem}
				disabled={busy || !draftValid}
				class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
			>
				{editingId != null ? 'Save item' : 'Add item'}
			</button>
			<button onclick={cancelEditor} class="text-sm text-neutral-400 hover:text-neutral-200">Cancel</button>
		</div>
	</div>
{/snippet}

<div class="flex gap-6">
	<!-- Protocol list -->
	<aside class="w-56 shrink-0">
		<h2 class="text-sm font-semibold text-neutral-300">Protocols</h2>
		{#if loading}
			<p class="mt-3 text-sm text-neutral-400">Loading…</p>
		{:else}
			<div class="mt-3 space-y-1">
				{#each protocols as p (p.id)}
					<button
						onclick={() => selectProtocol(p.id)}
						class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm {selectedId === p.id
							? 'bg-neutral-800 text-white'
							: 'text-neutral-300 hover:bg-neutral-900'}"
					>
						<span class="truncate">{p.name}</span>
						{#if p.is_active}<span class="ml-2 rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-300">ACTIVE</span>{/if}
					</button>
				{:else}
					<p class="text-sm text-neutral-500">No protocols yet.</p>
				{/each}
			</div>
			{#if canEdit}
				<div class="mt-3 space-y-2">
					<input
						placeholder="New protocol name…"
						bind:value={newName}
						onkeydown={(e) => e.key === 'Enter' && createProtocol()}
						class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
					/>
					<button
						onclick={createProtocol}
						disabled={busy || !newName.trim()}
						class="w-full rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
					>
						＋ Protocol
					</button>
				</div>
			{/if}
		{/if}
	</aside>

	<!-- Protocol editor -->
	<section class="min-w-0 flex-1">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !protocol}
			<p class="text-sm text-neutral-500">Select or create a protocol.</p>
		{:else}
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-lg font-semibold">{protocol.name}</h1>
					<p class="text-xs text-neutral-500">
						{protocol.items.length} item{protocol.items.length === 1 ? '' : 's'}
						{!isTemplate && protocol.is_active ? '· active' : ''}
					</p>
				</div>
				{#if canEdit}
					<div class="flex items-center gap-2 text-sm">
						{#if isTemplate}
							<button onclick={() => onApply?.(protocol!.id, protocol!.name)} class="rounded-full bg-brand px-3 py-1 font-medium text-white">Apply to client…</button>
						{:else if !protocol.is_active}
							<button onclick={activate} class="rounded-full border border-emerald-800 px-3 py-1 text-emerald-300 hover:bg-emerald-950">Set active</button>
						{/if}
						<button onclick={removeProtocol} class="rounded-full border border-neutral-800 px-3 py-1 text-neutral-400 hover:text-red-300">Delete</button>
					</div>
				{/if}
			</div>

			{#if loadingDetail}<p class="mt-4 text-sm text-neutral-400">Loading…</p>{/if}

			<div class="mt-4 space-y-2">
				{#each protocol.items as item (item.id)}
					<div class="rounded-lg border border-neutral-800">
						<div class="flex items-center justify-between px-3 py-2">
							<div class="min-w-0">
								<div class="flex items-center gap-2">
									<span class="font-medium">{item.item_name}</span>
									<span class="rounded bg-neutral-800 px-1.5 py-0.5 text-[10px] uppercase text-neutral-400">
										{item.supplement ? 'supplement' : 'compound'}
									</span>
								</div>
								<div class="mt-0.5 truncate text-xs text-neutral-500">{itemSummary(item)}</div>
								{#if item.target_benefit}<div class="text-xs text-neutral-600">{item.target_benefit}</div>{/if}
							</div>
							{#if canEdit}
								<div class="flex shrink-0 items-center gap-2 text-xs">
									<button onclick={() => openEdit(item)} class="text-orange-400 hover:text-orange-300">Edit</button>
									<button onclick={() => removeItem(item)} class="text-neutral-600 hover:text-red-300">✕</button>
								</div>
							{/if}
						</div>
						{#if editingId === item.id}
							<div class="px-3 pb-3">{@render editor()}</div>
						{/if}
					</div>
				{:else}
					<p class="text-sm text-neutral-600">No items yet.</p>
				{/each}
			</div>

			{#if canEdit}
				{#if adding}
					<div class="mt-3">{@render editor()}</div>
				{:else}
					<button onclick={openAdd} class="mt-3 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ Add item</button>
				{/if}
			{/if}
		{/if}
	</section>
</div>
