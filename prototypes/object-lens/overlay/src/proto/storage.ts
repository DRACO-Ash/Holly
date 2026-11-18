// Where the browser refuses storage (the prototype embedded from a file, which gets an opaque
// origin), an in-memory store stands in, so Holly's pages and the test console still run. Results
// then last only until the page closes; the console says so.
function works(): boolean {
  try {
    const probe = "holly.proto.probe";
    globalThis.localStorage.setItem(probe, "1");
    globalThis.localStorage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

class MemoryStorage implements Storage {
  private items = new Map<string, string>();
  get length(): number {
    return this.items.size;
  }
  clear(): void {
    this.items.clear();
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
  setItem(key: string, value: string): void {
    this.items.set(key, String(value));
  }
}

export const storagePersists = works();
if (!storagePersists) {
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: new MemoryStorage() });
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, value: new MemoryStorage() });
}
