<script lang="ts">
	import { onMount } from 'svelte';
	import {
		diaryApi,
		isPhoto,
		type Pose,
		type ProgressPhoto
	} from '$lib/diary/api';
	import { todayISO } from '$lib/diary/calc';
	import Button from '$lib/components/ui/Button.svelte';

	let poses = $state<Pose[]>([]);
	let photos = $state<ProgressPhoto[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Filter
	let filterPose = $state<number | null>(null);

	// Upload form
	let uploadPose = $state<number | null>(null);
	let takenOn = $state(todayISO());
	let file = $state<File | null>(null);
	let notes = $state('');
	let uploading = $state(false);
	// Ghost overlay: latest photo for the chosen pose, shown faint behind the picker.
	let ghost = $state<ProgressPhoto | null>(null);

	// Comparison
	let compareA = $state<number | null>(null);
	let compareB = $state<number | null>(null);

	async function loadPhotos() {
		photos = await diaryApi.photos(filterPose ? { pose: filterPose } : {});
	}

	onMount(async () => {
		try {
			poses = await diaryApi.poses();
			await loadPhotos();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function onUploadPoseChange() {
		ghost = null;
		if (uploadPose == null) return;
		const latest = await diaryApi.latestForPose(uploadPose);
		if (isPhoto(latest)) ghost = latest;
	}

	function onFile(e: Event) {
		const input = e.target as HTMLInputElement;
		file = input.files?.[0] ?? null;
	}

	async function upload(e: SubmitEvent) {
		e.preventDefault();
		if (!file) {
			error = 'Choose a photo first.';
			return;
		}
		uploading = true;
		error = null;
		try {
			await diaryApi.uploadPhoto({
				image: file,
				taken_on: takenOn,
				pose: uploadPose,
				notes
			});
			file = null;
			notes = '';
			// reset the file input
			const el = document.getElementById('photo-file') as HTMLInputElement | null;
			if (el) el.value = '';
			await loadPhotos();
			await onUploadPoseChange(); // refresh ghost to the just-uploaded shot
		} catch (err) {
			error = (err as Error).message;
		} finally {
			uploading = false;
		}
	}

	async function remove(id: number) {
		if (!confirm('Delete this photo?')) return;
		await diaryApi.deletePhoto(id);
		await loadPhotos();
	}

	const photoA = $derived(photos.find((p) => p.id === compareA));
	const photoB = $derived(photos.find((p) => p.id === compareB));
</script>

<a class="text-sm text-neutral-400 hover:text-white" href="/diary">← Diary</a>
<h1 class="mt-1 text-xl font-semibold">Progress photos</h1>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error && photos.length === 0 && poses.length === 0}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<!-- Upload with ghost overlay -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<h2 class="font-medium">Add a photo</h2>
		<div class="mt-3 grid gap-4 sm:grid-cols-2">
			<form class="space-y-3" onsubmit={upload}>
				<label class="block text-xs text-neutral-500">
					Pose
					<select
						bind:value={uploadPose}
						onchange={onUploadPoseChange}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						<option value={null}>Freeform (no pose)</option>
						{#each poses as p (p.id)}
							<option value={p.id}>{p.name}</option>
						{/each}
					</select>
				</label>
				<label class="block text-xs text-neutral-500">
					Date
					<input
						type="date"
						bind:value={takenOn}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					/>
				</label>
				<label class="block text-xs text-neutral-500">
					Photo
					<input
						id="photo-file"
						type="file"
						accept="image/*"
						capture="environment"
						onchange={onFile}
						class="mt-1 block w-full text-sm text-neutral-300 file:mr-3 file:rounded file:border-0 file:bg-neutral-800 file:px-3 file:py-1.5 file:text-neutral-200"
					/>
				</label>
				<label class="block text-xs text-neutral-500">
					Notes
					<input
						bind:value={notes}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					/>
				</label>
				{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
				<Button type="submit" disabled={uploading}>{uploading ? 'Uploading…' : 'Upload photo'}</Button>
			</form>

			<!-- Ghost overlay for consistent framing -->
			<div class="flex flex-col items-center justify-center rounded border border-dashed border-neutral-800 p-3">
				{#if ghost}
					<p class="mb-2 text-xs text-neutral-500">Last {ghost.pose_name} ({ghost.taken_on}) — match the framing</p>
					<img src={ghost.image_url} alt="Previous pose for framing reference" class="max-h-64 rounded opacity-40" />
				{:else}
					<p class="text-center text-xs text-neutral-600">
						Pick a pose you've shot before to see a faint overlay of your last photo here, so you can
						line up the same angle and distance.
					</p>
				{/if}
			</div>
		</div>
	</section>

	<!-- Comparison -->
	{#if photos.length >= 2}
		<section class="mt-6 rounded-lg border border-neutral-800 p-4">
			<h2 class="font-medium">Compare</h2>
			<div class="mt-2 grid grid-cols-2 gap-3">
				{#each [{ get: () => compareA, set: (v: number | null) => (compareA = v) }, { get: () => compareB, set: (v: number | null) => (compareB = v) }] as sel, i (i)}
					<select
						onchange={(e) => sel.set(e.currentTarget.value ? Number(e.currentTarget.value) : null)}
						class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						<option value="">Choose a photo…</option>
						{#each photos as p (p.id)}
							<option value={p.id}>{p.pose_name || 'Freeform'} · {p.taken_on}</option>
						{/each}
					</select>
				{/each}
			</div>
			{#if photoA || photoB}
				<div class="mt-3 grid grid-cols-2 gap-3">
					<div>
						{#if photoA}<img src={photoA.image_url} alt={`${photoA.pose_name} ${photoA.taken_on}`} class="w-full rounded" />
							<p class="mt-1 text-center text-xs text-neutral-500">{photoA.taken_on}</p>{/if}
					</div>
					<div>
						{#if photoB}<img src={photoB.image_url} alt={`${photoB.pose_name} ${photoB.taken_on}`} class="w-full rounded" />
							<p class="mt-1 text-center text-xs text-neutral-500">{photoB.taken_on}</p>{/if}
					</div>
				</div>
			{/if}
		</section>
	{/if}

	<!-- Gallery -->
	<section class="mt-6">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">Gallery</h2>
			<select
				bind:value={filterPose}
				onchange={loadPhotos}
				class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			>
				<option value={null}>All poses</option>
				{#each poses as p (p.id)}
					<option value={p.id}>{p.name}</option>
				{/each}
			</select>
		</div>
		{#if photos.length === 0}
			<p class="mt-3 text-sm text-neutral-500">No photos{filterPose ? ' for this pose' : ''} yet.</p>
		{:else}
			<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
				{#each photos as photo (photo.id)}
					<div class="group relative">
						<img
							src={photo.thumb_url}
							alt={`${photo.pose_name || 'Photo'} ${photo.taken_on}`}
							class="aspect-[3/4] w-full rounded object-cover"
							loading="lazy"
						/>
						<div class="mt-1 flex items-center justify-between">
							<span class="truncate text-[10px] text-neutral-500">
								{photo.pose_name || '—'} · {photo.taken_on}
							</span>
							<button
								class="text-[10px] text-neutral-600 hover:text-red-400"
								onclick={() => remove(photo.id)}>✕</button
							>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}
