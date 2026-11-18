// Keeps Tab and Shift Tab inside an open lens or Find while focus is in it. A listener on the
// document, scoped to the panel, so the panel itself needs no key handler.
import { useEffect, type RefObject } from "react";

const FOCUSABLE = "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [href]";

export function useFocusTrap(panel: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const box = panel.current;
      if (e.key !== "Tab" || !box?.contains(document.activeElement)) return;
      const focusable = box.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panel]);
}

// Closes an open lens or Find on a press outside it, on the backdrop or the page. The lens passes
// a handler that does nothing while Find is open over it, so only the topmost panel acts.
export function useOutsidePress(panel: RefObject<HTMLElement | null>, onOutside: () => void): void {
  useEffect(() => {
    const onPress = (e: MouseEvent) => {
      const target = e.target;
      if (!(target instanceof Node) || panel.current?.contains(target)) return;
      onOutside();
    };
    document.addEventListener("mousedown", onPress);
    return () => document.removeEventListener("mousedown", onPress);
  }, [panel, onOutside]);
}
