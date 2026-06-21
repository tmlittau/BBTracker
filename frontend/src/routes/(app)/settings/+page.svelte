<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getMe,
		updateMe,
		SEX_OPTIONS,
		UNIT_OPTIONS,
		type Me
	} from '$lib/api/profile';
	import { notificationsApi, type ReminderSettings } from '$lib/notifications/api';
	import { setSlotLabels } from '$lib/notifications/slots';
	import Button from '$lib/components/ui/Button.svelte';

	let me = $state<Me | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let saved = $state(false);

	// Reminder settings (delivered via Home Assistant).
	let reminders = $state<ReminderSettings | null>(null);
	let savingReminders = $state(false);
	let remindersSaved = $state(false);
	let testMsg = $state<string | null>(null);
	const TIME_SLOTS = [
		['waking', 'Waking'],
		['am', 'AM'],
		['noon', 'Noon'],
		['pm', 'PM'],
		['night', 'Night']
	] as const;

	function normalizeTimes(r: ReminderSettings): ReminderSettings {
		return {
			...r,
			waking: r.waking.slice(0, 5),
			am: r.am.slice(0, 5),
			noon: r.noon.slice(0, 5),
			pm: r.pm.slice(0, 5),
			night: r.night.slice(0, 5)
		};
	}

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
		const r = await notificationsApi.settings().catch(() => null);
		if (r) {
			reminders = normalizeTimes(r);
			setSlotLabels(reminders);
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

	async function saveReminders(e: SubmitEvent) {
		e.preventDefault();
		if (!reminders) return;
		savingReminders = true;
		remindersSaved = false;
		try {
			reminders = normalizeTimes(await notificationsApi.updateSettings(reminders));
			setSlotLabels(reminders); // refresh the app-wide slot labels
			remindersSaved = true;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			savingReminders = false;
		}
	}

	async function sendTest() {
		testMsg = 'Sending…';
		try {
			const r = await notificationsApi.test();
			testMsg = r.ok
				? 'Sent! Check your phone.'
				: r.detail || 'No notification sent — check the Home Assistant settings on the server.';
		} catch {
			testMsg = 'Could not reach the server.';
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

	{#if reminders}
		<form class="mt-8 max-w-md space-y-4 border-t border-neutral-800 pt-6" onsubmit={saveReminders}>
			<div>
				<h2 class="font-medium">Reminders</h2>
				<p class="mt-1 text-xs text-neutral-500">
					Pushed to your phone via Home Assistant. Slot times use your timezone above.
				</p>
			</div>
			<label class="flex items-center gap-2 text-sm text-neutral-300">
				<input type="checkbox" bind:checked={reminders.enabled} /> Daily dose reminders
			</label>
			<label class="flex items-center gap-2 text-sm text-neutral-300">
				<input type="checkbox" bind:checked={reminders.rest_enabled} /> Rest-timer “Rest over” alert
			</label>
			<div class="space-y-2">
				<div class="flex items-center gap-2 text-xs uppercase tracking-wide text-neutral-500">
					<span class="flex-1">Slot name</span>
					<span class="w-28">Reminder time</span>
				</div>
				{#each TIME_SLOTS as [key, label] (key)}
					<div class="flex items-center gap-2">
						<input
							type="text"
							placeholder={label}
							maxlength="24"
							bind:value={reminders[`${key}_label`]}
							class="min-w-0 flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
						/>
						<input
							type="time"
							bind:value={reminders[key]}
							class="w-28 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
						/>
					</div>
				{/each}
				<p class="text-xs text-neutral-600">
					Rename the five daily slots to match your routine. Leave blank to keep the default
					({TIME_SLOTS.map(([, l]) => l).join(', ')}).
				</p>
			</div>
			{#if remindersSaved}<p class="text-sm text-green-400">Reminders saved.</p>{/if}
			<div class="flex flex-wrap items-center gap-3">
				<Button type="submit" disabled={savingReminders}>{savingReminders ? 'Saving…' : 'Save reminders'}</Button>
				<button type="button" class="text-sm text-orange-400 hover:text-orange-300" onclick={sendTest}>
					Send test notification
				</button>
			</div>
			{#if testMsg}<p class="text-xs text-neutral-400">{testMsg}</p>{/if}
		</form>
	{/if}
{/if}
