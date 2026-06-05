<script lang="ts">
	import { nutritionApi, type Food } from './api';

	let {
		onpick
	}: { onpick: (food: Food) => void } = $props();

	let query = $state('');
	let results = $state<Food[]>([]);
	let loading = $state(false);
	let open = $state(false);

	let timer: ReturnType<typeof setTimeout>;
	function onInput() {
		clearTimeout(timer);
		timer = setTimeout(search, 200);
	}

	async function search() {
		if (query.trim().length < 2) {
			results = [];
			open = false;
			return;
		}
		loading = true;
		try {
			results = await nutritionApi.foods(query.trim());
			open = true;
		} finally {
			loading = false;
		}
	}

	function pick(food: Food) {
		onpick(food);
		query = '';
		results = [];
		open = false;
	}
</script>

<div class="relative">
	<input
		placeholder="Search foods to add…"
		bind:value={query}
		oninput={onInput}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-indigo-500"
	/>
	{#if open && results.length > 0}
		<ul
			class="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded-md border border-neutral-700 bg-neutral-900 shadow-lg"
		>
			{#each results as food (food.id)}
				<li>
					<button
						class="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-neutral-800"
						onclick={() => pick(food)}
					>
						<span>
							{food.name}
							{#if food.brand}<span class="text-neutral-500">· {food.brand}</span>{/if}
						</span>
						{#if !food.is_global}
							<span class="rounded bg-indigo-900 px-1.5 py-0.5 text-xs text-indigo-300">Custom</span>
						{/if}
					</button>
				</li>
			{/each}
		</ul>
	{:else if open && !loading}
		<p class="absolute z-10 mt-1 w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-500">
			No matches.
		</p>
	{/if}
</div>
