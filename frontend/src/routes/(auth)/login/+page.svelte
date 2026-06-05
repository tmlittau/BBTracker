<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { ensureCsrf, login, signup } from '$lib/api/auth';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	let mode = $state<'login' | 'signup'>('login');
	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let loading = $state(false);

	onMount(() => {
		void ensureCsrf();
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		loading = true;
		try {
			const res = mode === 'login' ? await login(email, password) : await signup(email, password);
			if (res.requires2fa) {
				await goto('/2fa');
			} else if (res.ok) {
				await goto('/dashboard');
			} else {
				error = res.error ?? 'Something went wrong';
			}
		} finally {
			loading = false;
		}
	}
</script>

<div class="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4">
	<div>
		<h1 class="text-2xl font-bold">BBTracker</h1>
		<p class="text-sm text-neutral-400">Self-coaching, all in one place.</p>
	</div>

	<form class="flex flex-col gap-3" onsubmit={submit}>
		<Input type="email" placeholder="Email" required bind:value={email} />
		<Input type="password" placeholder="Password" required bind:value={password} />
		{#if error}
			<p class="text-sm text-red-400">{error}</p>
		{/if}
		<Button type="submit" disabled={loading}>
			{loading ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
		</Button>
	</form>

	<button
		class="text-sm text-neutral-400 hover:text-neutral-200"
		onclick={() => (mode = mode === 'login' ? 'signup' : 'login')}
	>
		{mode === 'login' ? 'Need an account? Sign up' : 'Have an account? Log in'}
	</button>
</div>
