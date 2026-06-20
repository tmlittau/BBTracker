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

	// Comparison: pick a pose, then two dates (left/right) where it was shot.
	let comparePose = $state<number | null>(null);
	let compareA = $state<number | null>(null);
	let compareB = $state<number | null>(null);

	async function loadPhotos() {
		// Load everything once; the gallery filter + comparison work client-side.
		photos = await diaryApi.photos({});
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

	// Photos grouped by pose for comparison — only poses with ≥2 shots are comparable.
	type CompareGroup = { key: number; label: string; photos: ProgressPhoto[] };
	const byDate = (a: ProgressPhoto, b: ProgressPhoto) => a.taken_on.localeCompare(b.taken_on);
	const compareGroups = $derived.by<CompareGroup[]>(() => {
		const groups: CompareGroup[] = [];
		for (const pose of poses) {
			const ps = photos.filter((p) => p.pose === pose.id).sort(byDate);
			if (ps.length >= 2) groups.push({ key: pose.id, label: pose.name, photos: ps });
		}
		const free = photos.filter((p) => p.pose == null).sort(byDate);
		if (free.length >= 2) groups.push({ key: -1, label: 'Freeform', photos: free });
		return groups;
	});
	const comparePhotos = $derived(compareGroups.find((g) => g.key === comparePose)?.photos ?? []);

	// Default the pose to the first comparable group, and the two dates to
	// earliest vs latest — the most useful first-vs-last progress comparison.
	$effect(() => {
		if (compareGroups.length && !compareGroups.some((g) => g.key === comparePose)) {
			comparePose = compareGroups[0].key;
		}
	});
	$effect(() => {
		const list = comparePhotos;
		if (!list.length) return;
		if (!list.some((p) => p.id === compareA)) compareA = list[0].id;
		if (!list.some((p) => p.id === compareB)) compareB = list[list.length - 1].id;
	});

	const photoA = $derived(comparePhotos.find((p) => p.id === compareA));
	const photoB = $derived(comparePhotos.find((p) => p.id === compareB));
	const daysApart = $derived(
		photoA && photoB
			? Math.abs(Math.round((Date.parse(photoB.taken_on) - Date.parse(photoA.taken_on)) / 86400000))
			: null
	);

	// Gallery is client-filtered from the single photo list.
	const galleryPhotos = $derived(filterPose ? photos.filter((p) => p.pose === filterPose) : photos);
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

	<!-- Comparison: pick a pose, then two dates -->
	{#if compareGroups.length}
		<section class="mt-6 rounded-lg border border-neutral-800 p-4">
			<h2 class="font-medium">Compare</h2>
			<p class="mt-0.5 text-xs text-neutral-500">Pick a pose, then two dates to compare side by side.</p>
			<div class="mt-3 grid gap-3 sm:grid-cols-3">
				<label class="block text-xs text-neutral-500">
					Pose
					<select
						bind:value={comparePose}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						{#each compareGroups as g (g.key)}
							<option value={g.key}>{g.label} ({g.photos.length})</option>
						{/each}
					</select>
				</label>
				<label class="block text-xs text-neutral-500">
					Left date
					<select
						bind:value={compareA}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						{#each comparePhotos as p (p.id)}
							<option value={p.id}>{p.taken_on}</option>
						{/each}
					</select>
				</label>
				<label class="block text-xs text-neutral-500">
					Right date
					<select
						bind:value={compareB}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						{#each comparePhotos as p (p.id)}
							<option value={p.id}>{p.taken_on}</option>
						{/each}
					</select>
				</label>
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
				{#if daysApart != null && daysApart > 0}
					<p class="mt-2 text-center text-xs text-neutral-500">
						{daysApart} days apart{#if daysApart >= 14} (~{Math.round(daysApart / 7)} weeks){/if}
					</p>
				{/if}
			{/if}
		</section>
	{/if}

	<!-- Gallery -->
	<section class="mt-6">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">Gallery</h2>
			<select
				bind:value={filterPose}
				class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			>
				<option value={null}>All poses</option>
				{#each poses as p (p.id)}
					<option value={p.id}>{p.name}</option>
				{/each}
			</select>
		</div>
		{#if galleryPhotos.length === 0}
			<p class="mt-3 text-sm text-neutral-500">No photos{filterPose ? ' for this pose' : ''} yet.</p>
		{:else}
			<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
				{#each galleryPhotos as photo (photo.id)}
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
