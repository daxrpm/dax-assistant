type Listener = () => void;

/** Keeps a shared resource alive while it has consumers, including route hand-offs. */
export class DemandLifecycle {
  private readonly listeners = new Set<Listener>();
  private closeTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly start: () => void,
    private readonly stop: () => void,
    private readonly persistUntilShutdown = false,
  ) {}

  subscribe = (listener: Listener) => {
    if (this.closeTimer) {
      clearTimeout(this.closeTimer);
      this.closeTimer = null;
    }
    const wasEmpty = this.listeners.size === 0;
    this.listeners.add(listener);
    if (wasEmpty) this.start();

    return () => {
      this.listeners.delete(listener);
      if (this.persistUntilShutdown) return;
      if (this.listeners.size > 0 || this.closeTimer) return;
      // React cleans up the old route before subscribing the new route. Waiting
      // one task prevents needless disconnects during that hand-off and StrictMode.
      this.closeTimer = setTimeout(() => {
        this.closeTimer = null;
        if (this.listeners.size === 0) this.stop();
      }, 0);
    };
  };

  emit() {
    for (const listener of this.listeners) listener();
  }

  shutdown() {
    if (this.closeTimer) clearTimeout(this.closeTimer);
    this.closeTimer = null;
    this.stop();
  }
}
