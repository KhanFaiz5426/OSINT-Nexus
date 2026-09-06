import { Menu } from "lucide-react";

interface HeaderProps {
  onMenuToggle: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  return (
    <header className="flex h-11 shrink-0 items-center gap-4 border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-4">
      <button
        onClick={onMenuToggle}
        className="rounded-md p-1 text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] lg:hidden"
      >
        <Menu className="h-4 w-4" />
      </button>
      <span className="text-xs font-semibold tracking-wider text-[var(--nx-accent)] uppercase">
        OSINT Nexus
      </span>
      <div className="flex-1" />
      <div className="text-[10px] text-[var(--nx-text-muted)] font-mono">v0.1.0</div>
    </header>
  );
}
