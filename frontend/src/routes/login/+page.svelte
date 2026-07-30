<script lang="ts">
	import { goto } from '$app/navigation';
	import { login, completeMfa, fetchMe, logout, currentUser, MfaRequired } from '$lib/api/auth';

	let email = $state('');
	let password = $state('');
	let code = $state('');
	let mfaStep = $state(false);
	let loading = $state(false);
	let error = $state<string | null>(null);

	async function finish() {
		const me = await fetchMe();
		if (!me.is_coach) {
			await logout();
			error = 'That account is not enabled for coaching.';
			mfaStep = false;
			return;
		}
		currentUser.set(me);
		await goto('/');
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		loading = true;
		error = null;
		try {
			await login(email, password);
			await finish();
		} catch (err) {
			if (err instanceof MfaRequired) {
				mfaStep = true;
			} else {
				error = (err as Error).message;
			}
		} finally {
			loading = false;
		}
	}

	async function submitCode(e: SubmitEvent) {
		e.preventDefault();
		loading = true;
		error = null;
		try {
			await completeMfa(code);
			await finish();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	function back() {
		mfaStep = false;
		code = '';
		error = null;
	}
</script>

<div class="grid min-h-screen place-items-center px-6">
	{#if !mfaStep}
		<form class="w-full max-w-sm space-y-4" onsubmit={submit}>
			<div class="text-center">
				<h1 class="text-2xl font-bold text-gradient">TML Signal</h1>
				<p class="text-sm text-neutral-500">Coach Console</p>
			</div>
			<input
				type="email"
				placeholder="Email"
				bind:value={email}
				autocomplete="username"
				class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
			/>
			<input
				type="password"
				placeholder="Password"
				bind:value={password}
				autocomplete="current-password"
				class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
			/>
			{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
			<button
				type="submit"
				disabled={loading || !email || !password}
				class="w-full rounded-full bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
			>
				{loading ? 'Signing in…' : 'Sign in'}
			</button>
		</form>
	{:else}
		<form class="w-full max-w-sm space-y-4" onsubmit={submitCode}>
			<div class="text-center">
				<h1 class="text-2xl font-bold text-gradient">TML Signal</h1>
				<p class="text-sm text-neutral-500">Enter your authenticator code</p>
			</div>
			<input
				inputmode="numeric"
				autocomplete="one-time-code"
				placeholder="6-digit code"
				bind:value={code}
				class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-center text-lg tracking-widest text-neutral-100"
			/>
			{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
			<button
				type="submit"
				disabled={loading || !code.trim()}
				class="w-full rounded-full bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
			>
				{loading ? 'Verifying…' : 'Verify'}
			</button>
			<button type="button" onclick={back} class="w-full text-center text-xs text-neutral-500 hover:text-neutral-300">
				← Back
			</button>
		</form>
	{/if}
</div>
