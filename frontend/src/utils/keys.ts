// React keys for a list whose items carry no id, such as the assistant's output, which may
// repeat an item: each key is the item's content, and a repeat takes the first occurrence
// number ("#2", "#3") that no earlier key holds, so no two keys match whatever the content.
export function withContentKeys<T>(
  items: readonly T[],
  contentOf: (item: T) => string,
): { key: string; item: T }[] {
  const issued = new Set<string>();
  return items.map((item) => {
    const content = contentOf(item);
    let key = content;
    for (let n = 2; issued.has(key); n++) key = `${content}#${n}`;
    issued.add(key);
    return { key, item };
  });
}
