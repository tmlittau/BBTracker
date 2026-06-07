<script lang="ts">
	import { onMount } from 'svelte';
	import { dndzone } from 'svelte-dnd-action';
	import {
		nutritionApi,
		MEAL_SUGGESTIONS,
		type DailySummary,
		type DiaryEntry,
		type Food,
		type Meal
	} from '$lib/nutrition/api';
	import { microColor, num, barWidth, macroBarColor } from '$lib/nutrition/calc';
	import { isoDate, shiftISODate } from '$lib/date';
	import MacroBar from '$lib/nutrition/MacroBar.svelte';
	import FoodSearch from '$lib/nutrition/FoodSearch.svelte';
	import AddEntryDialog from '$lib/nutrition/AddEntryDialog.svelte';
	import FoodCreateModal from '$lib/nutrition/FoodCreateModal.svelte';

	function todayISO(): string {
		return isoDate();
	}

	let date = $state(todayISO());
	let summary = $state<DailySummary | null>(null);
	let entries = $state<DiaryEntry[]>([]);
	let meals = $state<Meal[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Top headline block flips between the macro and micro view via arrow buttons.
	let topView = $state<'macro' | 'micro'>('macro');

	let pendingFood = $state<Food | null>(null);
	let pendingMealId = $state<number | null>(null);
	let newMealName = $state('');

	// "＋ New food" while adding to a meal: remember the meal, open the modal, then
	// drop straight into the add-to-meal dialog once it's created.
	let showFoodModal = $state(false);
	let pendingMealForNew = $state<number | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			[summary, entries, meals] = await Promise.all([
				nutritionApi.summary(date),
				nutritionApi.diary(date),
				nutritionApi.meals(date)
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function shiftDate(days: number) {
		date = shiftISODate(date, days);
		load();
	}

	function entriesFor(mealId: number): DiaryEntry[] {
		return entries.filter((e) => e.meal === mealId);
	}

	async function addMeal(name: string) {
		const n = name.trim();
		if (!n) return;
		await nutritionApi.createMeal({ date, name: n, order: meals.length });
		newMealName = '';
		meals = await nutritionApi.meals(date);
	}
	async function renameMeal(m: Meal, name: string) {
		const n = name.trim();
		if (!n || n === m.name) return;
		m.name = n;
		await nutritionApi.updateMeal(m.id, { name: n }).catch((e) => (error = (e as Error).message));
	}
	async function deleteMeal(id: number) {
		if (!confirm('Delete this meal and its foods?')) return;
		await nutritionApi.deleteMeal(id);
		await load();
	}
	async function copyYesterday() {
		await nutritionApi.copyYesterdayMeals(date);
		meals = await nutritionApi.meals(date);
	}

	// meal reorder: drag + arrow fallback
	function persistMealOrder() {
		return nutritionApi.reorderMeals(meals.map((m, i) => ({ id: m.id, order: i })));
	}
	function dndConsider(e: CustomEvent<{ items: Meal[] }>) {
		meals = e.detail.items;
	}
	async function dndFinalize(e: CustomEvent<{ items: Meal[] }>) {
		meals = e.detail.items;
		await persistMealOrder();
	}
	async function moveMeal(i: number, dir: -1 | 1) {
		const j = i + dir;
		if (j < 0 || j >= meals.length) return;
		const arr = [...meals];
		[arr[i], arr[j]] = [arr[j], arr[i]];
		meals = arr;
		await persistMealOrder();
	}

	function startAdd(food: Food, mealId: number) {
		pendingFood = food;
		pendingMealId = mealId;
	}
	function openNewFood(mealId: number) {
		pendingMealForNew = mealId;
		showFoodModal = true;
	}
	function onFoodCreated(food: Food) {
		if (pendingMealForNew != null) startAdd(food, pendingMealForNew);
		pendingMealForNew = null;
	}
	async function confirmAdd(data: { serving: number | null; quantity: string }) {
		if (!pendingFood || pendingMealId == null) return;
		try {
			await nutritionApi.logEntry({
				date,
				meal: pendingMealId,
				food: pendingFood.id,
				serving: data.serving,
				quantity: data.quantity
			});
			pendingFood = null;
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}
	async function removeEntry(id: number) {
		await nutritionApi.deleteEntry(id);
		await load();
	}

	const macro = (slug: string) => summary?.nutrients.find((n) => n.slug === slug);
	const micros = $derived(
		(summary?.nutrients ?? []).filter((n) => n.category === 'vitamin' || n.category === 'mineral')
	);
	const pendingMealName = $derived(meals.find((m) => m.id === pendingMealId)?.name ?? 'meal');

	const microDot: Record<string, string> = {
		green: 'bg-green-500',
		amber: 'bg-amber-500',
		red: 'bg-red-500',
		none: 'bg-neutral-600'
	};
</script>

<h1 class="text-xl font-semibold">Nutrition</h1>

<!-- Date navigator -->
<div class="mt-4 flex items-center justify-between rounded-lg border border-neutral-800 px-3 py-2">
	<button class="px-2 text-neutral-400 hover:text-white" onclick={() => shiftDate(-1)}>‹ Prev</button>
	<div class="flex items-center gap-3">
		<input
			type="date"
			bind:value={date}
			onchange={load}
			class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100"
		/>
		{#if date !== todayISO()}
			<button class="text-xs text-indigo-400 hover:text-indigo-300" onclick={() => { date = todayISO(); load(); }}>Today</button>
		{/if}
	</div>
	<button class="px-2 text-neutral-400 hover:text-white" onclick={() => shiftDate(1)}>Next ›</button>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if summary}
	<!-- Headline: macro ⇄ micro toggle -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4" data-testid="macro-summary">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">{topView === 'macro' ? 'Macros' : 'Micronutrients'}</h2>
			<div class="flex items-center gap-2 text-neutral-400">
				<button
					class="rounded px-2 py-0.5 hover:bg-neutral-800 hover:text-white"
					aria-label="Previous view"
					onclick={() => (topView = topView === 'macro' ? 'micro' : 'macro')}
				>‹</button>
				<span class="text-xs tabular-nums">{topView === 'macro' ? '1 / 2' : '2 / 2'}</span>
				<button
					class="rounded px-2 py-0.5 hover:bg-neutral-800 hover:text-white"
					aria-label="Next view"
					onclick={() => (topView = topView === 'macro' ? 'micro' : 'macro')}
				>›</button>
			</div>
		</div>

		{#if !summary.has_target}
			<p class="mt-2 text-xs text-amber-400">
				No active target — <a class="underline" href="/nutrition/targets">set one</a> to track progress.
			</p>
		{/if}

		{#if topView === 'macro'}
			<div class="mt-3 grid gap-4 sm:grid-cols-2">
				<MacroBar nutrient={macro('energy')} big color={macroBarColor('energy')} />
				<MacroBar nutrient={macro('protein')} big color={macroBarColor('protein')} />
				<MacroBar nutrient={macro('carbohydrate')} big color={macroBarColor('carbohydrate')} />
				<MacroBar nutrient={macro('fat')} big color={macroBarColor('fat')} />
			</div>
		{:else}
			<p class="mt-2 text-xs text-neutral-500">
				Dot shows progress to target/RDA (<span class="text-green-400">met</span>,
				<span class="text-amber-400">partial</span>, <span class="text-red-400">low</span>); the bar
				fills as you consume.
			</p>
			<div class="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
				{#each micros as n (n.id)}
					<div class="text-sm">
						<div class="flex items-center justify-between">
							<span class="flex items-center gap-2">
								<span class="h-2 w-2 rounded-full {microDot[microColor(n.percent)]}"></span>
								{n.name}
							</span>
							<span class="text-neutral-400">
								{num(n.amount).toFixed(1)}{#if n.target}<span class="text-neutral-600">/{num(n.target).toFixed(0)}</span>{/if}
								{n.unit}
							</span>
						</div>
						<div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-neutral-800/60">
							<div class="h-1.5 rounded-full bg-neutral-500" style="width: {barWidth(n.percent)}%"></div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- Meals (dynamic per day) -->
	{#if meals.length === 0}
		<p class="mt-6 text-sm text-neutral-500">No meals yet — add one below to start logging food.</p>
	{:else}
		<section
			class="mt-6 space-y-5"
			use:dndzone={{ items: meals, flipDurationMs: 150, dropTargetStyle: {} }}
			onconsider={dndConsider}
			onfinalize={dndFinalize}
		>
			{#each meals as m, mi (m.id)}
				<div class="rounded-lg border border-neutral-800 p-4">
					<div class="flex items-center justify-between gap-2">
						<div class="flex items-center gap-2">
							<span class="cursor-grab select-none text-neutral-600" aria-hidden="true">⠿</span>
							<input
								class="w-full rounded bg-transparent font-medium text-neutral-100 outline-none focus:bg-neutral-900 focus:px-2 focus:py-1 sm:w-48"
								value={m.name}
								aria-label="Meal name"
								onchange={(e) => renameMeal(m, e.currentTarget.value)}
							/>
						</div>
						<div class="flex items-center gap-2 text-xs text-neutral-500">
							<button class="hover:text-white disabled:opacity-30" aria-label="Move up" disabled={mi === 0} onclick={() => moveMeal(mi, -1)}>↑</button>
							<button class="hover:text-white disabled:opacity-30" aria-label="Move down" disabled={mi === meals.length - 1} onclick={() => moveMeal(mi, 1)}>↓</button>
							<button class="text-red-400 hover:text-red-300" onclick={() => deleteMeal(m.id)}>Delete</button>
						</div>
					</div>

					{#if entriesFor(m.id).length > 0}
						<ul class="mt-2 divide-y divide-neutral-800">
							{#each entriesFor(m.id) as entry (entry.id)}
								<li class="flex items-center justify-between py-2 text-sm">
									<span>
										{entry.item_name}
										<span class="text-neutral-500">· {entry.grams ?? entry.quantity} {entry.unit}</span>
									</span>
									<button class="text-xs text-neutral-600 hover:text-red-400" aria-label="Remove entry" onclick={() => removeEntry(entry.id)}>✕</button>
								</li>
							{/each}
						</ul>
					{/if}

					<div class="mt-3 flex items-start gap-2">
						<div class="flex-1"><FoodSearch onpick={(food) => startAdd(food, m.id)} /></div>
						<button
							class="shrink-0 rounded-md border border-neutral-700 px-3 py-2 text-sm text-emerald-300 hover:border-emerald-600"
							onclick={() => openNewFood(m.id)}
						>
							＋ New food
						</button>
					</div>
				</div>
			{/each}
		</section>
	{/if}

	<!-- Add a meal -->
	<div class="mt-4 flex flex-wrap items-center gap-2">
		<input
			placeholder="Add a meal…"
			bind:value={newMealName}
			onkeydown={(e) => { if (e.key === 'Enter') addMeal(newMealName); }}
			class="w-40 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100"
		/>
		<button class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500" onclick={() => addMeal(newMealName)}>+ Add meal</button>
		{#each MEAL_SUGGESTIONS as s (s)}
			<button class="rounded-full border border-neutral-700 px-2.5 py-0.5 text-xs text-neutral-400 hover:border-neutral-500" onclick={() => addMeal(s)}>{s}</button>
		{/each}
		<button class="ml-auto text-xs text-indigo-400 hover:text-indigo-300" onclick={copyYesterday}>Copy yesterday's meals</button>
	</div>
{/if}

{#if pendingFood}
	<AddEntryDialog
		food={pendingFood}
		meal={pendingMealName}
		onconfirm={confirmAdd}
		oncancel={() => (pendingFood = null)}
	/>
{/if}

<FoodCreateModal bind:open={showFoodModal} oncreated={onFoodCreated} onclose={() => (pendingMealForNew = null)} />
