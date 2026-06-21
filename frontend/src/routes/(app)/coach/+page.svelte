<script lang="ts">
	import { onMount } from 'svelte';
	import { coachApi, type ClientBrief, type CoachLink } from '$lib/coaching/clients';

	let clients = $state<ClientBrief[]>([]);
	let sent = $state<CoachLink[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let inviteEmail = $state('');
	let inviting = $state(false);
	let inviteMsg = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			[clients, { sent }] = await Promise.all([coachApi.clients(), coachApi.invites()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(load);

	async function invite(e: SubmitEvent) {
		e.preventDefault();
		if (!inviteEmail.trim()) return;
		inviting = true;
		inviteMsg = null;
		try {
			await coachApi.invite(inviteEmail.trim());
			inviteEmail = '';
			inviteMsg = 'Invite sent — your client needs to accept it.';
			await load();
		} catch (err) {
			inviteMsg = (err as Error).message.replace(/^POST .*?→ \d+\s*/, '') || 'Could not invite.';
		} finally {
			inviting = false;
		}
	}

	async function revoke(link: CoachLink) {
		if (!confirm(`End the coaching link with ${link.client_email}?`)) return;
		await coachApi.revoke(link.id);
		await load();
	}

	const pendingSent = $derived(sent.filter((l) => l.status === 'pending'));
</script>

<h1 class="text-xl font-semibold">Coaching</h1>
<p class="mt-1 text-sm text-neutral-400">
	View and review your clients' progress. Clients must accept your invite before you can see their
	data, and can revoke access at any time.
</p>

<form class="mt-6 flex flex-wrap items-end gap-3" onsubmit={invite}>
	<div class="flex-1 min-w-[16rem]">
		<label class="text-xs text-neutral-500" for="invite-email">Invite a client by email</label>
		<input
			id="invite-email"
			type="email"
			bind:value={inviteEmail}
			placeholder="client@example.com"
			class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
		/>
	</div>
	<button
		type="submit"
		disabled={inviting}
		class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
	>
		{inviting ? 'Inviting…' : 'Send invite'}
	</button>
</form>
{#if inviteMsg}<p class="mt-2 text-sm text-neutral-300">{inviteMsg}</p>{/if}

{#if loading}
	<p class="mt-8 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-8 text-red-400">{error}</p>
{:else}
	<section class="mt-8">
		<h2 class="font-medium">Clients</h2>
		{#if clients.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No active clients yet — invite one above.</p>
		{:else}
			<div class="mt-3 grid gap-3 sm:grid-cols-2">
				{#each clients as c (c.client_id)}
					<a
						href={`/coach/clients/${c.client_id}`}
						class="group rounded-lg border border-neutral-800 bg-neutral-900 p-4 hover:border-neutral-700"
					>
						<div class="flex items-center justify-between">
							<span class="font-medium text-neutral-100 group-hover:text-white">{c.name}</span>
							{#if c.phase}<span class="text-xs text-amber-300">{c.phase}</span>{/if}
						</div>
						<div class="mt-2 flex items-center gap-4 text-xs text-neutral-400">
							<span>{c.bodyweight != null ? `${c.bodyweight} kg` : '— kg'}</span>
							<span>last check-in {c.last_check_in ?? '—'}</span>
						</div>
					</a>
				{/each}
			</div>
		{/if}
	</section>

	{#if pendingSent.length > 0}
		<section class="mt-8">
			<h2 class="font-medium">Pending invites</h2>
			<ul class="mt-3 space-y-2">
				{#each pendingSent as l (l.id)}
					<li
						class="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm"
					>
						<span class="text-neutral-300">{l.client_email} <span class="text-neutral-500">· awaiting acceptance</span></span>
						<button class="text-xs text-red-400 hover:text-red-300" onclick={() => revoke(l)}>Cancel</button>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
{/if}
