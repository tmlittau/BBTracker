<script lang="ts">
	import { onMount } from 'svelte';
	import { coachingApi, type ClientBrief, type UserResult } from '$lib/coaching/api';
	import { fetchMe, type Me } from '$lib/api/auth';

	let clients = $state<ClientBrief[]>([]);
	let me = $state<Me | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let msg = $state<string | null>(null);

	// Add-client search
	let showAdd = $state(false);
	let query = $state('');
	let results = $state<UserResult[]>([]);
	let searching = $state(false);
	let addingId = $state<number | null>(null);
	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	const selfCoaching = $derived(me != null && clients.some((c) => c.client_id === me!.id));

	async function load() {
		loading = true;
		error = null;
		try {
			[clients, me] = await Promise.all([coachingApi.clients(), me ? Promise.resolve(me) : fetchMe()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function onQueryInput() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(search, 250);
	}
	async function search() {
		const q = query.trim();
		if (q.length < 2) {
			results = [];
			return;
		}
		searching = true;
		try {
			results = await coachingApi.searchUsers(q);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			searching = false;
		}
	}

	async function add(u: UserResult) {
		addingId = u.id;
		error = null;
		msg = null;
		try {
			await coachingApi.invite(u.email);
			msg =
				u.relationship === 'self'
					? "You're now coaching yourself."
					: `Invite sent to ${u.name || u.email}.`;
			await load();
			await search(); // refresh relationship labels
		} catch (e) {
			error = (e as Error).message;
		} finally {
			addingId = null;
		}
	}

	async function coachSelf() {
		if (!me) return;
		await add({ id: me.id, email: me.email, name: '', relationship: 'self' });
	}

	const relLabel: Record<UserResult['relationship'], string> = {
		self: 'You',
		active: 'Active client',
		pending: 'Invite pending',
		declined: 'Declined',
		revoked: 'Revoked',
		none: ''
	};
</script>

<div class="p-6">
	<div class="flex items-start justify-between gap-4">
		<div>
			<h1 class="text-xl font-semibold">Roster</h1>
			<p class="text-sm text-neutral-500">Your active clients. Open one for the full workspace.</p>
		</div>
		<div class="flex items-center gap-2">
			{#if me && !selfCoaching}
				<button
					onclick={coachSelf}
					disabled={addingId === me.id}
					class="rounded-full border border-neutral-700 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
				>
					Coach yourself
				</button>
			{/if}
			<button
				onclick={() => (showAdd = !showAdd)}
				class="rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white"
			>
				{showAdd ? 'Close' : '＋ Add client'}
			</button>
		</div>
	</div>

	{#if showAdd}
		<div class="mt-4 max-w-lg rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
			<label class="text-xs text-neutral-500" for="user-search">Search registered users by name or email</label>
			<input
				id="user-search"
				placeholder="Search users…"
				bind:value={query}
				oninput={onQueryInput}
				class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100"
			/>
			<div class="mt-2 max-h-72 space-y-1 overflow-y-auto">
				{#if searching}
					<p class="px-1 py-1.5 text-xs text-neutral-500">Searching…</p>
				{:else if query.trim().length >= 2 && results.length === 0}
					<p class="px-1 py-1.5 text-xs text-neutral-500">No users found.</p>
				{:else}
					{#each results as u (u.id)}
						<div class="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-neutral-800/60">
							<div class="min-w-0">
								<div class="truncate text-sm text-neutral-100">{u.name || u.email}</div>
								{#if u.name}<div class="truncate text-[11px] text-neutral-500">{u.email}</div>{/if}
							</div>
							{#if u.relationship === 'none' || u.relationship === 'self' || u.relationship === 'declined' || u.relationship === 'revoked'}
								<button
									onclick={() => add(u)}
									disabled={addingId === u.id}
									class="shrink-0 rounded-full bg-brand px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
								>
									{u.relationship === 'self' ? 'Coach yourself' : u.relationship === 'none' ? 'Add' : 'Re-invite'}
								</button>
							{:else}
								<span class="shrink-0 text-xs text-neutral-500">{relLabel[u.relationship]}</span>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
			<p class="mt-1 text-[11px] text-neutral-600">
				New clients get a pending invite they accept in the app. Adding yourself is active immediately.
			</p>
		</div>
	{/if}

	{#if msg}<p class="mt-4 text-sm text-emerald-400">{msg}</p>{/if}
	{#if error}<p class="mt-4 text-sm text-red-400">{error}</p>{/if}

	{#if loading}
		<p class="mt-6 text-neutral-400">Loading…</p>
	{:else if clients.length === 0}
		<p class="mt-6 text-neutral-500">No active clients yet. Use “＋ Add client” to add one.</p>
	{:else}
		<table class="mt-6 w-full text-sm">
			<thead class="text-left text-xs uppercase tracking-wide text-neutral-500">
				<tr class="border-b border-neutral-800">
					<th class="py-2">Client</th>
					<th class="py-2">Phase</th>
					<th class="py-2">Last check-in</th>
					<th class="py-2 text-right">Bodyweight</th>
					<th class="py-2 text-right">Edit</th>
				</tr>
			</thead>
			<tbody>
				{#each clients as c (c.client_id)}
					<tr class="border-b border-neutral-800/60 hover:bg-neutral-900/40">
						<td class="py-2.5">
							<a href={`/clients/${c.client_id}`} class="font-medium hover:text-orange-300">
								{c.name || c.email}
							</a>
							{#if me && c.client_id === me.id}<span class="ml-2 rounded bg-neutral-800 px-1.5 py-0.5 text-[10px] text-neutral-400">you</span>{/if}
						</td>
						<td class="py-2.5 text-neutral-400">{c.phase ?? '—'}</td>
						<td class="py-2.5 text-neutral-400">{c.last_check_in ?? '—'}</td>
						<td class="py-2.5 text-right tabular-nums text-neutral-300">{c.bodyweight ?? '—'}</td>
						<td class="py-2.5 text-right">
							{#if c.can_edit_prescriptions}
								<span class="text-xs text-emerald-400">✓</span>
							{:else}
								<span class="text-xs text-neutral-600">read-only</span>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>
