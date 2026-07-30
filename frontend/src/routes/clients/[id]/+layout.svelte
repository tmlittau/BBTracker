<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import { page } from '$app/stores';
	import { coachingApi, type ClientBrief } from '$lib/coaching/api';
	import { CLIENT_CTX, type ClientContext } from '$lib/clients/context';

	let { children } = $props();

	const clientId = $derived(Number($page.params.id));
	let brief = $state<ClientBrief | null>(null);

	// Expose the brief (esp. can_edit_prescriptions) to child tabs without a refetch.
	setContext<ClientContext>(CLIENT_CTX, {
		get brief() {
			return brief;
		},
		get canEdit() {
			return brief?.can_edit_prescriptions ?? false;
		}
	});

	onMount(async () => {
		try {
			const all = await coachingApi.clients();
			brief = all.find((c) => c.client_id === clientId) ?? null;
		} catch {
			brief = null;
		}
	});

	const tabs = $derived([
		{ href: `/clients/${clientId}`, label: 'Overview', exact: true },
		{ href: `/clients/${clientId}/nutrition`, label: 'Nutrition' },
		{ href: `/clients/${clientId}/training`, label: 'Training' },
		{ href: `/clients/${clientId}/protocols`, label: 'Protocols' },
		{ href: `/clients/${clientId}/bloodwork`, label: 'Bloodwork' },
		{ href: `/clients/${clientId}/phases`, label: 'Phases' },
		{ href: `/clients/${clientId}/library`, label: 'Library' }
	]);

	function isActive(href: string, exact: boolean) {
		return exact ? $page.url.pathname === href : $page.url.pathname.startsWith(href);
	}
</script>

<div class="border-b border-neutral-800 bg-neutral-900/40 px-6 pt-4">
	<div class="flex items-center justify-between">
		<div>
			<a href="/" class="text-xs text-neutral-500 hover:text-orange-300">← Roster</a>
			<h1 class="text-lg font-semibold">{brief?.name || brief?.email || `Client #${clientId}`}</h1>
		</div>
		{#if brief}
			<span
				class="rounded-full px-2.5 py-1 text-xs {brief.can_edit_prescriptions
					? 'bg-emerald-950 text-emerald-300'
					: 'bg-neutral-800 text-neutral-400'}"
			>
				{brief.can_edit_prescriptions ? '✎ You can edit this plan' : 'Read-only'}
			</span>
		{/if}
	</div>

	<nav class="mt-3 flex gap-1 text-sm">
		{#each tabs as t (t.href)}
			<a
				href={t.href}
				class="rounded-t-md px-3 py-2 {isActive(t.href, t.exact ?? false)
					? 'border-b-2 border-orange-500 text-white'
					: 'text-neutral-400 hover:text-white'}"
			>
				{t.label}
			</a>
		{/each}
	</nav>
</div>

{@render children()}
