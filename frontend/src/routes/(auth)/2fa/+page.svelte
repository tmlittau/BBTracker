<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import QRCode from 'qrcode';
	import { activateTotp, authenticate2fa, getTotpSecret, reauthenticate } from '$lib/api/auth';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	let mode = $state<'loading' | 'enroll' | 'authenticate'>('loading');
	let secret = $state<string | null>(null);
	let qr = $state<string | null>(null);
	let code = $state('');
	let password = $state('');
	// allauth requires a recent password confirmation before enabling 2FA.
	let reauthNeeded = $state(false);
	let error = $state<string | null>(null);
	let loading = $state(false);

	onMount(async () => {
		const s = await getTotpSecret();
		if (s) {
			secret = s;
			mode = 'enroll';
			const email = $page.data.user?.email ?? 'user';
			const uri = `otpauth://totp/BBTracker:${encodeURIComponent(email)}?secret=${s}&issuer=BBTracker`;
			qr = await QRCode.toDataURL(uri);
		} else {
			mode = 'authenticate';
		}
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		loading = true;
		try {
			if (mode === 'authenticate') {
				const res = await authenticate2fa(code);
				if (res.ok) await goto('/dashboard');
				else error = res.error ?? 'Invalid code';
				return;
			}

			// Enrollment. Confirm password first if allauth previously asked us to.
			if (reauthNeeded) {
				const re = await reauthenticate(password);
				if (!re.ok) {
					error = re.error ?? 'Password incorrect';
					return;
				}
				reauthNeeded = false;
			}

			const res = await activateTotp(code);
			if (res.ok) {
				await goto('/dashboard');
			} else if (res.needsReauth) {
				reauthNeeded = true;
				error = 'Please confirm your password to enable two-factor authentication.';
			} else {
				error = res.error ?? 'Invalid code';
			}
		} finally {
			loading = false;
		}
	}
</script>

<div class="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4">
	<h1 class="text-2xl font-bold">Two-factor authentication</h1>

	{#if mode === 'loading'}
		<p class="text-neutral-400">Loading…</p>
	{:else}
		{#if mode === 'enroll'}
			<p class="text-sm text-neutral-400">
				Scan this QR code with your authenticator app, then enter the 6-digit code to finish setup.
			</p>
			{#if qr}
				<img src={qr} alt="TOTP QR code" class="h-48 w-48 self-center rounded bg-white p-2" />
			{/if}
			{#if secret}
				<p class="break-all text-center text-xs text-neutral-500">Manual key: {secret}</p>
			{/if}
		{:else}
			<p class="text-sm text-neutral-400">Enter the 6-digit code from your authenticator app.</p>
		{/if}

		<form class="flex flex-col gap-3" onsubmit={submit}>
			{#if reauthNeeded}
				<Input type="password" placeholder="Confirm your password" required bind:value={password} />
			{/if}
			<Input type="text" placeholder="123456" required bind:value={code} />
			{#if error}
				<p class="text-sm text-red-400">{error}</p>
			{/if}
			<Button type="submit" disabled={loading}>
				{loading ? 'Verifying…' : reauthNeeded ? 'Confirm & enable' : 'Verify'}
			</Button>
		</form>
	{/if}
</div>
