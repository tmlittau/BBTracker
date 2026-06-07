<script lang="ts">
	// Web barcode scanner: live camera via getUserMedia + ZXing decoding. Works in any
	// modern browser incl. iOS Safari and the installed PWA — over HTTPS (or localhost),
	// which getUserMedia requires. No native app needed.
	import Modal from '$lib/components/ui/Modal.svelte';

	let { open = $bindable(false), onresult }: { open?: boolean; onresult: (code: string) => void } =
		$props();

	let videoEl = $state<HTMLVideoElement | null>(null);
	let error = $state<string | null>(null);
	let controls: { stop: () => void } | null = null;

	async function start() {
		error = null;
		stop();
		try {
			const { BrowserMultiFormatReader } = await import('@zxing/browser');
			const reader = new BrowserMultiFormatReader();
			// Prefer the rear camera for scanning product barcodes.
			controls = await reader.decodeFromConstraints(
				{ video: { facingMode: 'environment' } },
				videoEl!,
				(result) => {
					if (result) {
						const code = result.getText();
						stop();
						open = false;
						onresult(code);
					}
				}
			);
		} catch (e) {
			error =
				(e as Error)?.name === 'NotAllowedError'
					? 'Camera permission denied — allow camera access and try again.'
					: ((e as Error)?.message ?? 'Camera unavailable.');
		}
	}

	function stop() {
		controls?.stop();
		controls = null;
	}

	// Run the camera while the modal is open; tear it down when it closes/unmounts.
	$effect(() => {
		if (open && videoEl) start();
		return stop;
	});
</script>

<Modal bind:open title="Scan barcode" size="md" onclose={stop}>
	<!-- svelte-ignore a11y_media_has_caption -->
	<video
		bind:this={videoEl}
		class="mt-1 aspect-square w-full rounded bg-black object-cover"
		autoplay
		playsinline
		muted
	></video>
	{#if error}
		<p class="mt-2 text-sm text-red-400">{error}</p>
	{:else}
		<p class="mt-2 text-xs text-neutral-500">
			Point the camera at the product barcode (UPC/EAN). Needs camera permission and HTTPS.
		</p>
	{/if}
</Modal>
