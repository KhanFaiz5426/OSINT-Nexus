/**
 * Tailwind utility merger. Accepts strings, falsy values, and conditional
 * objects. Used by all components that need conditional class names.
 */

export type ClassValue =
  | string
  | number
  | null
  | false
  | undefined
  | ClassDictionary
  | ClassArray;

interface ClassDictionary {
  [id: string]: boolean | undefined | null;
}

type ClassArray = ClassValue[];

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const input of inputs) {
    if (!input) continue;
    if (typeof input === "string" || typeof input === "number") {
      out.push(String(input));
    } else if (Array.isArray(input)) {
      const sub = cn(...input);
      if (sub) out.push(sub);
    } else if (typeof input === "object") {
      for (const [k, v] of Object.entries(input)) {
        if (v) out.push(k);
      }
    }
  }
  return out.join(" ");
}
