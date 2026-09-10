import { LayoutDashboard, Search, Plus, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "../lib/utils";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Investigations", href: "/investigations", icon: Search },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar({ open, onClose }: SidebarProps) {
  const location = useLocation();

  function isActive(href: string) {
    if (href === "/") return location.pathname === "/";
    return location.pathname.startsWith(href);
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[56px] flex-col border-r border-[var(--nx-border)] bg-[var(--nx-surface-1)] transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Logo mark */}
        <div className="flex h-14 items-center justify-center border-b border-[var(--nx-border)]">
          <Link to="/" className="flex items-center justify-center" title="OSINT Nexus">
            <img src="/osint-nexus-logo.svg" alt="OSINT Nexus" className="h-8 w-8" />
            <span className="sr-only">OSINT Nexus</span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex flex-1 flex-col items-center gap-1 px-2 pt-3">
          {navigation.map((item) => (
            <Link
              key={item.name}
              to={item.href}
              title={item.name}
              className={cn(
                "relative flex h-9 w-9 items-center justify-center rounded-md transition-colors",
                isActive(item.href)
                  ? "bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]"
                  : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)]",
              )}
            >
              {isActive(item.href) && (
                <span className="absolute left-[-9px] h-5 w-[3px] rounded-r-full bg-[var(--nx-accent)]" />
              )}
              <item.icon className="h-[18px] w-[18px]" />
              <span className="sr-only">{item.name}</span>
            </Link>
          ))}

          {/* New Investigation button */}
          <Link
            to="/investigations/new"
            title="New Investigation"
            className="mt-2 flex h-9 w-9 items-center justify-center rounded-md bg-[var(--nx-accent)] text-[var(--nx-base)] transition-colors hover:bg-[var(--nx-accent)]/90"
          >
            <Plus className="h-[18px] w-[18px]" strokeWidth={2.5} />
            <span className="sr-only">New Investigation</span>
          </Link>
        </nav>

        {/* Bottom section */}
        <div className="flex flex-col items-center gap-2 border-t border-[var(--nx-border)] px-2 py-3">
          <span className="text-[9px] font-medium text-[var(--nx-text-muted)] [writing-mode:vertical-lr]">
            v0.1
          </span>
        </div>
      </aside>
    </>
  );
}

export const AppNav = Sidebar;
