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

/**
 * Auto-detect the target type from a user-entered string.
 * Returns one of the backend TargetType values.
 */
import type { TargetType } from "../api/investigations";

export function detectTargetType(input: string): TargetType {
  const v = input.trim();
  if (!v) return "unknown";

  // Email: contains @ with domain
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return "email";

  // URL: starts with http(s):// or contains path segments
  if (/^https?:\/\//i.test(v)) return "url";

  // IP: IPv4 or IPv6
  if (/^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/.test(v)) return "ip";
  if (/^[0-9a-f:]{3,39}$/i.test(v) && v.includes(":")) return "ip";

  // Domain: contains dots but isn't IP, no spaces
  if (/^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$/.test(v)) return "domain";

  // Organization: multi-word names with common suffixes or capitalized words
  if (/\b(Inc|LLC|Corp|Corporation|Company|Group|Foundation|Ltd|GmbH|S\.?A\.?|AG|Co\.?)\b/i.test(v)
    || (/\s/.test(v) && /^[A-Z]/.test(v))) return "organization";

  // Username: alphanumeric with possible special chars (including multi-word names like "john doe")
  if (/^[a-zA-Z0-9._ -]+$/.test(v) && v.length >= 2) return "username";

  return "unknown";
}

/** Labels and descriptions for target types. */
export const TARGET_TYPE_INFO: Record<string, { label: string; icon: string; placeholder: string }> = {
  domain: { label: "Domain", icon: "🌐", placeholder: "example.com" },
  ip: { label: "IP Address", icon: "📡", placeholder: "192.168.1.1" },
  url: { label: "URL", icon: "🔗", placeholder: "https://example.com/path" },
  email: { label: "Email", icon: "📧", placeholder: "user@example.com" },
  username: { label: "Username", icon: "👤", placeholder: "johndoe" },
  organization: { label: "Organization", icon: "🏢", placeholder: "Acme Corporation" },
  unknown: { label: "Unknown", icon: "❓", placeholder: "Enter a target..." },
};
