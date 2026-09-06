import { useState, useEffect } from "react";
import {
  X,
  Crosshair,
  Loader2,
  Globe,
  MonitorSmartphone,
  Link2,
  Mail,
  User,
  Building2,
  HelpCircle,
  ArrowRight,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { useCreateInvestigation, useStartInvestigation } from "../hooks/useApi";
import { detectTargetType, TARGET_TYPE_INFO, cn } from "../lib/utils";
import type { InvestigationCreate, TargetType } from "../api/investigations";

const TARGET_ICONS: Record<string, typeof Globe> = {
  domain: Globe,
  ip: MonitorSmartphone,
  url: Link2,
  email: Mail,
  username: User,
  organization: Building2,
  unknown: HelpCircle,
};

const DEPTH_OPTIONS = [
  { value: "shallow", label: "Shallow", desc: "Fast scan, core nodes" },
  { value: "standard", label: "Standard", desc: "Balanced correlation" },
  { value: "deep", label: "Deep", desc: "Exhaustive correlation" },
] as const;

export function NewInvestigationModal() {
  const newModalOpen = useWorkspaceStore((s) => s.newModalOpen);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);
  const openTab = useWorkspaceStore((s) => s.openTab);

  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [depth, setDepth] = useState<"shallow" | "standard" | "deep">("standard");
  const [detectedType, setDetectedType] = useState<TargetType>("unknown");
  const [manualType, setManualType] = useState<TargetType | null>(null);

  const createMutation = useCreateInvestigation();
  const startMutation = useStartInvestigation();

  useEffect(() => {
    if (newModalOpen) {
      setTarget("");
      setName("");
      setDepth("standard");
      setManualType(null);
    }
  }, [newModalOpen]);

  useEffect(() => {
    const detected = detectTargetType(target);
    setDetectedType(detected);
  }, [target]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && newModalOpen) {
        setNewModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [newModalOpen, setNewModalOpen]);

  if (!newModalOpen) return null;

  const currentType = manualType || detectedType;
  const TypeIcon = TARGET_ICONS[currentType] ?? HelpCircle;
  const typeInfo = TARGET_TYPE_INFO[currentType] || TARGET_TYPE_INFO.unknown;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim() || createMutation.isPending) return;

    const payload: InvestigationCreate = {
      name: name.trim() || `Investigation: ${target.trim()}`,
      target: target.trim(),
      depth,
    };

    createMutation.mutate(payload, {
      onSuccess: (result) => {
        // Automatically start the investigation
        startMutation.mutate(result.id);

        // Open in workspace tabs & activate
        openTab({
          id: result.id,
          target: result.target,
          name: result.name,
          target_type: result.target_type,
          status: "running",
        });

        setNewModalOpen(false);
      },
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="w-full max-w-lg rounded-lg border border-[var(--nx-border-strong)] bg-[var(--nx-surface-1)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--nx-border)] px-4 py-3 bg-[var(--nx-surface-2)]">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]">
              <Crosshair className="h-3.5 w-3.5" />
            </div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-primary)]">
              New Investigation Workspace
            </h2>
          </div>
          <button
            onClick={() => setNewModalOpen(false)}
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Main Prompt & Target Input */}
          <div>
            <label
              htmlFor="modal-target-input"
              className="block text-sm font-semibold text-[var(--nx-text-primary)] mb-1.5"
            >
              What do you want to investigate?
            </label>
            <div className="relative">
              <input
                id="modal-target-input"
                type="text"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                autoFocus
                placeholder="domain / IP / URL / email / username / organization"
                className="block w-full rounded-md border border-[var(--nx-border-strong)] bg-[var(--nx-surface-2)] px-3 py-2.5 text-sm font-mono text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--nx-accent)] transition-colors"
                autoComplete="off"
              />
            </div>

            {/* Target Type: Auto-detect Indicator */}
            <div className="mt-2 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[var(--nx-text-tertiary)]">Target type:</span>
                <span className="inline-flex items-center gap-1 rounded bg-[var(--nx-surface-3)] border border-[var(--nx-border)] px-2 py-0.5 text-xs font-medium text-[var(--nx-text-secondary)]">
                  <TypeIcon className="h-3 w-3 text-[var(--nx-accent)]" />
                  <span>
                    {target.trim() ? `Auto-detect (${typeInfo.label})` : "Auto-detect"}
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Investigation Depth */}
          <div>
            <label className="block text-xs font-medium uppercase tracking-wider text-[var(--nx-text-tertiary)] mb-1.5">
              Investigation Depth
            </label>
            <div className="grid grid-cols-3 gap-2">
              {DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDepth(opt.value)}
                  className={cn(
                    "flex flex-col items-start rounded-md border p-2.5 text-left transition-all",
                    depth === opt.value
                      ? "border-[var(--nx-accent)] bg-[var(--nx-accent-subtle)] text-[var(--nx-text-primary)]"
                      : "border-[var(--nx-border)] bg-[var(--nx-surface-2)] text-[var(--nx-text-tertiary)] hover:border-[var(--nx-border-strong)] hover:text-[var(--nx-text-secondary)]",
                  )}
                >
                  <span className="text-xs font-semibold text-[var(--nx-text-primary)]">
                    {opt.label}
                  </span>
                  <span className="text-[10px] text-[var(--nx-text-muted)] leading-tight mt-0.5">
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Optional Name */}
          <div>
            <label
              htmlFor="modal-name-input"
              className="block text-xs text-[var(--nx-text-muted)] mb-1"
            >
              Investigation title (optional)
            </label>
            <input
              id="modal-name-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={target.trim() ? `Investigation: ${target.trim()}` : "Auto-generated"}
              className="block w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2.5 py-1.5 text-xs text-[var(--nx-text-secondary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent)] focus:outline-none"
            />
          </div>

          {/* Errors */}
          {createMutation.isError && (
            <div className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-400">
              {createMutation.error.message}
            </div>
          )}

          {/* Footer actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--nx-border)]">
            <button
              type="button"
              onClick={() => setNewModalOpen(false)}
              className="rounded px-3 py-1.5 text-xs font-medium text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!target.trim() || createMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded bg-[var(--nx-accent)] px-4 py-1.5 text-xs font-semibold text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Launching Workspace...</span>
                </>
              ) : (
                <>
                  <span>Start Investigation</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
