<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getMe,
		updateMe,
		SEX_OPTIONS,
		UNIT_OPTIONS,
		type Me
	} from '$lib/api/profile';
	import Button from '$lib/components/ui/Button.svelte';

	let me = $state<Me | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let saved = $state(false);

	// Editable form fields (strings for inputs/selects).
	let firstName = $state('');
	let sex = $state('unspecified');
	let dob = $state('');
	let heightCm = $state('');
	let unitSystem = $state('metric');
	let timezone = $state('UTC');

	function hydrate(m: Me) {
		me = m;
		firstName = m.first_name ?? '';
		sex = m.profile.sex;
		dob = m.profile.date_of_birth ?? '';
		heightCm = m.profile.height_cm ?? '';
		unitSystem = m.profile.unit_system;
		timezone = m.profile.timezone;
	}

	onMount(async () => {
		try {
			hydrate(await getMe());
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		saved = false;
		error = null;
		try {
			const updated = await updateMe({
				first_name: firstName,
				profile: {
					sex,
					date_of_birth: dob === '' ? null : dob,
					height_cm: heightCm === '' ? null : heightCm,
					unit_system: unitSystem,
					timezone
				}
			});
			hydrate(updated);
			saved = true;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<h1 class="text-xl font-semibold">Settings</h1>
<p class="mt-1 text-sm text-neutral-400">Your profile. Setting your sex enables sex-specific reference ranges in bloodwork.</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error && !me}
	<p class="mt-6 text-red-400">{error}</p>
{:else if me}
	<form class="mt-6 max-w-md space-y-4" onsubmit={save}>
		<div>
			<label class="text-xs text-neutral-500" for="email">Email</label>
			<input
				id="email"
				value={me.email}
				disabled
				class="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-500"
			/>
			<p class="mt-1 text-xs text-neutral-600">Email can't be changed here.</p>
		</div>

		<div>
			<label class="text-xs text-neutral-500" for="first_name">First name</label>
			<input
				id="first_name"
				name="first_name"
				bind:value={firstName}
				class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
			/>
		</div>

		<div>
			<label class="text-xs text-neutral-500" for="sex">Sex</label>
			<select
				id="sex"
				name="sex"
				bind:value={sex}
				class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
			>
				{#each SEX_OPTIONS as o (o.value)}
					<option value={o.value}>{o.label}</option>
				{/each}
			</select>
			<p class="mt-1 text-xs text-neutral-600">
				Used for sex-specific bloodwork reference ranges (e.g. testosterone, hematocrit).
			</p>
		</div>

		<div class="flex gap-3">
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="dob">Date of birth</label>
				<input
					id="dob"
					name="date_of_birth"
					type="date"
					bind:value={dob}
					class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
				/>
			</div>
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="height">Height (cm)</label>
				<input
					id="height"
					name="height_cm"
					type="number"
					step="0.1"
					bind:value={heightCm}
					class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
				/>
			</div>
		</div>

		<div class="flex gap-3">
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="units">Units</label>
				<select
					id="units"
					name="unit_system"
					bind:value={unitSystem}
					class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
				>
					{#each UNIT_OPTIONS as o (o.value)}
						<option value={o.value}>{o.label}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1">
				<label class="text-xs text-neutral-500" for="tz">Timezone</label>
				<input
					id="tz"
					name="timezone"
					bind:value={timezone}
					class="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100"
				/>
			</div>
		</div>

		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		{#if saved}<p class="text-sm text-green-400">Saved.</p>{/if}
		<Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</Button>
	</form>
{/if}
