<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		clientPlan,
		writeError,
		type ClientPlan,
		type MealPlan,
		type MealPlanMeal,
		type MealPlanItem,
		type PlanMacros,
		type Food
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

	let plans = $state<MealPlan[]>([]);
	let selectedId = $state<number | null>(null);
	let current = $state<MealPlan | null>(null);
	let loading = $state(true);
	let loadingDetail = $state(false);
	let error = $state<string | null>(null);
	let newPlanName = $state('');
	let busy = $state(false);

	const kcal = (m?: PlanMacros) => Math.round(Number(m?.energy ?? 0));
	const macroSummary = (m?: PlanMacros) =>
		`${kcal(m)} kcal · ${Math.round(Number(m?.protein ?? 0))}P / ${Math.round(Number(m?.carbohydrate ?? 0))}C / ${Math.round(Number(m?.fat ?? 0))}F`;

	async function loadList(select?: number) {
		loading = true;
		error = null;
		try {
			plans = await plan.mealPlans();
			const pick = select ?? selectedId ?? plans[0]?.id ?? null;
			if (pick != null) await selectPlan(pick);
			else current = null;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function selectPlan(id: number) {
		selectedId = id;
		loadingDetail = true;
		try {
			current = await plan.mealPlan(id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loadingDetail = false;
		}
	}
	async function refresh() {
		if (selectedId == null) return;
		current = await plan.mealPlan(selectedId);
		// keep the left-list row's headline kcal in sync after item edits
		const row = plans.find((p) => p.id === selectedId);
		if (row) row.macros = current.macros;
	}

	onMount(() => loadList());

	async function createPlan() {
		if (!newPlanName.trim()) return;
		busy = true;
		error = null;
		try {
			const p = await plan.createMealPlan({ name: newPlanName.trim() });
			newPlanName = '';
			await loadList(p.id);
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function renamePlan(name: string) {
		if (!current || name.trim() === current.name || !name.trim()) return;
		try {
			await plan.updateMealPlan(current.id, { name: name.trim() });
			current.name = name.trim();
			const row = plans.find((p) => p.id === current!.id);
			if (row) row.name = name.trim();
		} catch (e) {
			error = writeError(e);
		}
	}
	async function saveNotes(notes: string) {
		if (!current || notes === current.notes) return;
		try {
			await plan.updateMealPlan(current.id, { notes });
			current.notes = notes;
		} catch (e) {
			error = writeError(e);
		}
	}

	async function removePlan() {
		if (!current || !confirm(`Delete meal plan “${current.name}”?`)) return;
		try {
			await plan.deleteMealPlan(current.id);
			selectedId = null;
			current = null;
			await loadList();
		} catch (e) {
			error = writeError(e);
		}
	}

	async function addMeal() {
		if (!current) return;
		try {
			await plan.createPlanMeal({ plan: current.id, name: `Meal ${current.meals.length + 1}`, order: current.meals.length });
			await refresh();
		} catch (e) {
			error = writeError(e);
		}
	}
	async function renameMeal(meal: MealPlanMeal, name: string) {
		if (name.trim() === meal.name || !name.trim()) return;
		try {
			await plan.updatePlanMeal(meal.id, { name: name.trim() });
			meal.name = name.trim();
		} catch (e) {
			error = writeError(e);
		}
	}
	async function removeMeal(meal: MealPlanMeal) {
		if (!confirm(`Remove “${meal.name}” and its foods?`)) return;
		try {
			await plan.deletePlanMeal(meal.id);
			await refresh();
		} catch (e) {
			error = writeError(e);
		}
	}

	// --- food picker (one open meal at a time) ---
	let pickerMealId = $state<number | null>(null);
	let foodQuery = $state('');
	let foodResults = $state<Food[]>([]);
	let foodLoading = $state(false);
	let foodTimer: ReturnType<typeof setTimeout> | undefined;

	function openPicker(mealId: number) {
		pickerMealId = pickerMealId === mealId ? null : mealId;
		foodQuery = '';
		foodResults = [];
		if (pickerMealId != null) searchFoods();
	}
	function onFoodInput() {
		clearTimeout(foodTimer);
		foodTimer = setTimeout(searchFoods, 250);
	}
	async function searchFoods() {
		foodLoading = true;
		try {
			foodResults = (await plan.foods(foodQuery)).slice(0, 25);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			foodLoading = false;
		}
	}
	async function addFood(meal: MealPlanMeal, food: Food) {
		try {
			await plan.createPlanItem({ meal: meal.id, food: food.id, quantity: '100', order: meal.items.length });
			pickerMealId = null;
			await refresh();
		} catch (e) {
			error = writeError(e);
		}
	}
	async function setQty(item: MealPlanItem, value: string) {
		const q = value.trim();
		if (q === '' || q === item.quantity) return;
		try {
			await plan.updatePlanItem(item.id, { quantity: q });
			await refresh();
		} catch (e) {
			error = writeError(e);
		}
	}
	async function removeItem(item: MealPlanItem) {
		try {
			await plan.deletePlanItem(item.id);
			await refresh();
		} catch (e) {
			error = writeError(e);
		}
	}
</script>

<div class="flex gap-6">
	<!-- Plan list -->
	<aside class="w-56 shrink-0">
		<h2 class="text-sm font-semibold text-neutral-300">Meal plans</h2>
		{#if loading}
			<p class="mt-3 text-sm text-neutral-400">Loading…</p>
		{:else}
			<div class="mt-3 space-y-1">
				{#each plans as p (p.id)}
					<button
						onclick={() => selectPlan(p.id)}
						class="flex w-full flex-col items-start rounded-md px-3 py-2 text-left text-sm {selectedId === p.id
							? 'bg-neutral-800 text-white'
							: 'text-neutral-300 hover:bg-neutral-900'}"
					>
						<span class="truncate">{p.name}</span>
						<span class="text-[10px] text-neutral-500">{kcal(p.macros)} kcal</span>
					</button>
				{:else}
					<p class="text-sm text-neutral-500">No meal plans yet.</p>
				{/each}
			</div>
			{#if canEdit}
				<div class="mt-3 space-y-2">
					<input
						placeholder="New plan name…"
						bind:value={newPlanName}
						onkeydown={(e) => e.key === 'Enter' && createPlan()}
						class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
					/>
					<button
						onclick={createPlan}
						disabled={busy || !newPlanName.trim()}
						class="w-full rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
					>
						＋ Meal plan
					</button>
				</div>
			{/if}
		{/if}
	</aside>

	<!-- Plan editor -->
	<section class="min-w-0 flex-1">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !current}
			<p class="text-sm text-neutral-500">Select or create a meal plan.</p>
		{:else}
			<div class="flex items-start justify-between gap-4">
				<div class="min-w-0 flex-1">
					{#if canEdit}
						<input
							value={current.name}
							onblur={(e) => renamePlan(e.currentTarget.value)}
							onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
							class="w-full max-w-md rounded bg-transparent text-lg font-semibold text-neutral-100 hover:bg-neutral-900 focus:bg-neutral-900"
						/>
					{:else}
						<h1 class="text-lg font-semibold">{current.name}</h1>
					{/if}
					<p class="mt-0.5 text-xs text-neutral-400">
						Daily total: <span class="text-neutral-200">{macroSummary(current.macros)}</span>
					</p>
				</div>
				{#if canEdit}
					<div class="flex shrink-0 items-center gap-2 text-sm">
						{#if onApply}
							<button onclick={() => onApply?.(current!.id, current!.name)} class="rounded-full bg-brand px-3 py-1 font-medium text-white">Apply to client…</button>
						{/if}
						<button onclick={removePlan} class="rounded-full border border-neutral-800 px-3 py-1 text-neutral-400 hover:text-red-300">Delete</button>
					</div>
				{/if}
			</div>

			{#if canEdit}
				<textarea
					value={current.notes}
					onblur={(e) => saveNotes(e.currentTarget.value)}
					rows="1"
					placeholder="Plan notes (optional) — e.g. timing, prep tips…"
					class="mt-3 w-full max-w-2xl rounded border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200"
				></textarea>
			{:else if current.notes}
				<p class="mt-3 max-w-2xl text-sm text-neutral-400">{current.notes}</p>
			{/if}

			{#if loadingDetail}<p class="mt-3 text-sm text-neutral-400">Loading…</p>{/if}

			<div class="mt-4 max-w-2xl space-y-3">
				{#each current.meals as meal (meal.id)}
					<div class="rounded-lg border border-neutral-800">
						<div class="flex items-center gap-2 border-b border-neutral-800 px-3 py-2">
							{#if canEdit}
								<input
									value={meal.name}
									onblur={(e) => renameMeal(meal, e.currentTarget.value)}
									onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
									class="min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-sm font-medium text-neutral-100 hover:bg-neutral-900 focus:bg-neutral-900"
								/>
							{:else}
								<span class="flex-1 text-sm font-medium">{meal.name}</span>
							{/if}
							<span class="shrink-0 text-xs text-neutral-500">{macroSummary(meal.macros)}</span>
							{#if canEdit}
								<button onclick={() => removeMeal(meal)} class="shrink-0 text-xs text-neutral-500 hover:text-red-300">✕</button>
							{/if}
						</div>

						<div class="divide-y divide-neutral-900">
							{#each meal.items as item (item.id)}
								<div class="flex items-center gap-2 px-3 py-2">
									<div class="min-w-0 flex-1">
										<div class="truncate text-sm text-neutral-100">{item.food_brand ? `${item.food_brand} · ` : ''}{item.food_name}</div>
										<div class="text-xs text-neutral-500">{kcal(item.macros)} kcal · {Math.round(Number(item.macros?.protein ?? 0))}P / {Math.round(Number(item.macros?.carbohydrate ?? 0))}C / {Math.round(Number(item.macros?.fat ?? 0))}F</div>
									</div>
									{#if canEdit}
										<input
											type="number"
											min="0"
											step="1"
											value={item.quantity}
											onchange={(e) => setQty(item, e.currentTarget.value)}
											class="w-20 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-right text-xs text-neutral-100"
										/>
										<span class="w-6 text-xs text-neutral-500">{item.food_unit}</span>
										<button onclick={() => removeItem(item)} class="text-xs text-neutral-600 hover:text-red-300">✕</button>
									{:else}
										<span class="text-xs text-neutral-400">{Math.round(Number(item.quantity))} {item.food_unit}</span>
									{/if}
								</div>
							{:else}
								<div class="px-3 py-2 text-sm text-neutral-600">No foods yet.</div>
							{/each}
						</div>

						{#if canEdit}
							<div class="border-t border-neutral-800 px-3 py-2">
								<button onclick={() => openPicker(meal.id)} class="text-xs text-orange-400 hover:text-orange-300">
									{pickerMealId === meal.id ? 'Close' : '＋ Add food'}
								</button>
								{#if pickerMealId === meal.id}
									<div class="mt-2 rounded-md border border-neutral-800 bg-neutral-950 p-2">
										<input
											placeholder="Search foods…"
											bind:value={foodQuery}
											oninput={onFoodInput}
											class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
										/>
										<div class="mt-2 max-h-56 space-y-0.5 overflow-y-auto">
											{#if foodLoading}
												<p class="px-1 py-2 text-xs text-neutral-500">Searching…</p>
											{:else}
												{#each foodResults as f (f.id)}
													<button onclick={() => addFood(meal, f)} class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm text-neutral-200 hover:bg-neutral-800">
														<span class="truncate">{f.brand ? `${f.brand} · ` : ''}{f.name}</span>
														<span class="ml-2 shrink-0 text-[10px] text-neutral-500">/ 100 {f.unit}</span>
													</button>
												{:else}
													<p class="px-1 py-2 text-xs text-neutral-500">No matches.</p>
												{/each}
											{/if}
										</div>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>

			{#if canEdit}
				<button onclick={addMeal} class="mt-4 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ Add meal</button>
			{/if}
		{/if}
	</section>
</div>
