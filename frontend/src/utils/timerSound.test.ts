import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A stand-in for the browser's AudioContext that records each tone it is asked to play.
interface Tone {
  frequency: number;
  wave: { type: string };
  start: number;
  stop: number;
  ramps: [number, number][];
  startValue: [number, number] | null;
}

const constructed: FakeContext[] = [];

class FakeContext {
  state: "suspended" | "running" | "closed" = "suspended";
  currentTime = 10;
  destination = { kind: "speakers" };
  tones: Tone[] = [];
  resume = vi.fn(async () => {
    this.state = "running";
  });

  constructor() {
    constructed.push(this);
  }

  createOscillator() {
    const wave = { type: "" };
    const tone: Tone = { frequency: 0, wave, start: -1, stop: -1, ramps: [], startValue: null };
    this.tones.push(tone);
    return Object.assign(wave, {
      frequency: {
        set value(v: number) {
          tone.frequency = v;
        },
      },
      connect: vi.fn(),
      start: (at: number) => {
        tone.start = at;
      },
      stop: (at: number) => {
        tone.stop = at;
      },
    });
  }

  createGain() {
    const tones = this.tones;
    return {
      connect: vi.fn(),
      gain: {
        setValueAtTime: (value: number, at: number) => {
          tones[tones.length - 1].startValue = [value, at];
        },
        linearRampToValueAtTime: (value: number, at: number) => {
          tones[tones.length - 1].ramps.push([value, at]);
        },
      },
    };
  }
}

async function freshModule() {
  vi.resetModules();
  return import("./timerSound");
}

beforeEach(() => {
  constructed.length = 0;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("the timer sounds", () => {
  it("do nothing outside a browser", async () => {
    const sound = await freshModule();
    expect(() => {
      sound.unlockAudio();
      sound.playPreAlert();
      sound.playFiring();
      vi.runAllTimers();
    }).not.toThrow();
  });

  it("do nothing in a browser with no Web Audio", async () => {
    vi.stubGlobal("window", {});
    const sound = await freshModule();
    sound.unlockAudio();
    sound.playFiring();
    vi.runAllTimers();
    expect(constructed).toHaveLength(0);
  });

  it("stay silent until the first gesture unlocks the audio", async () => {
    vi.stubGlobal("window", { AudioContext: FakeContext });
    const sound = await freshModule();
    sound.playPreAlert();
    vi.runAllTimers();
    const context = constructed[0];
    expect(context.tones).toHaveLength(0);
    sound.unlockAudio();
    expect(context.resume).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    sound.unlockAudio();
    expect(context.resume).toHaveBeenCalledTimes(1);
    expect(constructed).toHaveLength(1);
  });

  it("chime two rising notes for a pre-alert", async () => {
    vi.stubGlobal("window", { AudioContext: FakeContext });
    const sound = await freshModule();
    sound.unlockAudio();
    await Promise.resolve();
    sound.playPreAlert();
    const context = constructed[0];
    expect(context.tones.map((t) => t.frequency)).toEqual([660]);
    vi.advanceTimersByTime(220);
    expect(context.tones.map((t) => t.frequency)).toEqual([660, 880]);
    const [first] = context.tones;
    expect(first.wave.type).toBe("sine");
    expect(first.startValue).toEqual([0, 10]);
    expect(first.ramps).toEqual([
      [0.18, 10.01],
      [0, 10.18],
    ]);
    expect(first.start).toBe(10);
    expect(first.stop).toBeCloseTo(10.2);
  });

  it("beep three times, the last higher and longer, when a timer fires", async () => {
    vi.stubGlobal("window", { AudioContext: FakeContext });
    const sound = await freshModule();
    sound.unlockAudio();
    await Promise.resolve();
    sound.playFiring();
    vi.advanceTimersByTime(440);
    const context = constructed[0];
    expect(context.tones.map((t) => t.frequency)).toEqual([880, 880, 1040]);
    expect(context.tones.map((t) => t.ramps[0][0])).toEqual([0.22, 0.22, 0.22]);
    expect(context.tones[2].ramps[1]).toEqual([0, 10.24]);
  });

  it("use the prefixed context where the plain one is missing, and replace a closed one", async () => {
    vi.stubGlobal("window", { webkitAudioContext: FakeContext });
    const sound = await freshModule();
    sound.unlockAudio();
    expect(constructed).toHaveLength(1);
    constructed[0].state = "closed";
    sound.unlockAudio();
    expect(constructed).toHaveLength(2);
    expect(constructed[1].resume).toHaveBeenCalledTimes(1);
  });
});
