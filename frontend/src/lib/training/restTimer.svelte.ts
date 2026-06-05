// Rest timer as a runes-based store. Supports two modes:
//   • count-up   (default) — freeform rest, turns amber once past `target`.
//   • countdown  — starts at a per-set rest target and ticks down to 0.
// We always track real `elapsed` seconds from a wall-clock start (robust across
// tab throttling); `remaining`/`display` derive from it.

class RestTimer {
	elapsed = $state(0);
	running = $state(false);
	target = $state(90); // seconds
	mode = $state<'up' | 'down'>('up');
	#handle: ReturnType<typeof setInterval> | null = null;
	#startMs = 0;

	start(targetSeconds?: number, opts?: { countdown?: boolean }) {
		if (targetSeconds != null && Number.isFinite(targetSeconds)) this.target = targetSeconds;
		this.mode = opts?.countdown ? 'down' : 'up';
		this.#startMs = Date.now();
		this.elapsed = 0;
		this.running = true;
		this.#handle && clearInterval(this.#handle);
		this.#handle = setInterval(() => {
			this.elapsed = Math.floor((Date.now() - this.#startMs) / 1000);
		}, 250);
	}

	stop() {
		this.running = false;
		if (this.#handle) {
			clearInterval(this.#handle);
			this.#handle = null;
		}
	}

	reset() {
		this.stop();
		this.elapsed = 0;
	}

	/** Seconds left in countdown mode (0 once finished). */
	get remaining(): number {
		return Math.max(0, this.target - this.elapsed);
	}

	/** The number to show: countdown shows time left, count-up shows time elapsed. */
	get display(): number {
		return this.mode === 'down' ? this.remaining : this.elapsed;
	}

	/** Countdown has reached/passed zero. */
	get done(): boolean {
		return this.mode === 'down' && this.elapsed >= this.target;
	}

	/** Warning state: count-up past target, or countdown finished (rest is over). */
	get overTarget(): boolean {
		return this.running && this.elapsed >= this.target;
	}
}

export const restTimer = new RestTimer();
