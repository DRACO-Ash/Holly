import { useEffect, useState } from "react";

// The time now, moved on every `stepMs`, so relative times ("3 min ago") stay true on screen.
export function useNow(stepMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), stepMs);
    return () => window.clearInterval(id);
  }, [stepMs]);
  return now;
}
