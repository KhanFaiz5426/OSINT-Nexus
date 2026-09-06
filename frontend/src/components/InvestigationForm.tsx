import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { useCreateInvestigation } from "../hooks/useApi";
import { detectTargetType, TARGET_TYPE_INFO, cn } from "../lib/utils";
import type { InvestigationCreate, TargetType } from "../api/investigations";
import { useState, useEffect } from "react";
import { Globe, MonitorSmartphone, Link2, Mail, User, Building2, HelpCircle, Loader2, Crosshair, ArrowRight } from "lucide-react";

const formSchema = z.object({
  name: z.string().max(200).optional(),
  target: z.string().min(1, "Target is required").max(500),
  depth: z.enum(["shallow", "standard", "deep"]),
});

type FormData = z.infer<typeof formSchema>;

const depthOptions = [
  { value: "shallow", label: "Shallow", desc: "Quick scan, minimal API usage", time: "~1 min" },
  { value: "standard", label: "Standard", desc: "Balanced depth and coverage", time: "~3 min" },
  { value: "deep", label: "Deep", desc: "Thorough analysis, full budget", time: "~10 min" },
] as const;

const TARGET_ICONS: Record<string, typeof Globe> = {
  domain: Globe,
  ip: MonitorSmartphone,
  url: Link2,
  email: Mail,
  username: User,
  organization: Building2,
  unknown: HelpCircle,
};

export function InvestigationForm() {
  const navigate = useNavigate();
  const [detectedType, setDetectedType] = useState<TargetType>("unknown");

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema) as never,
    defaultValues: { depth: "standard", target: "", name: "" },
  });

  const targetValue = watch("target");

  useEffect(() => {
    setDetectedType(detectTargetType(targetValue || ""));
  }, [targetValue]);

  const mutation = useCreateInvestigation();

  const onSubmit = (data: FormData) => {
    const payload: InvestigationCreate = {
      name: data.name?.trim() || `Investigation: ${data.target}`,
      target: data.target,
      depth: data.depth,
    };
    mutation.mutate(payload, {
      onSuccess: (result) => navigate(`/investigations/${result.id}`),
    });
  };

  const TypeIcon = TARGET_ICONS[detectedType] ?? HelpCircle;
  const typeInfo = TARGET_TYPE_INFO[detectedType];

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-2xl space-y-8">
      {/* Target input */}
      <div>
        <div className="relative">
          <div className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2">
            <Crosshair className="h-5 w-5 text-[var(--nx-accent)]" />
          </div>
          <input
            id="target-input"
            type="text"
            {...register("target")}
            className="block w-full rounded-lg border border-[var(--nx-border-strong)] bg-[var(--nx-surface-2)] py-4 pl-12 pr-4 text-lg font-mono text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent-dim)] focus:outline-none focus:ring-1 focus:ring-[var(--nx-accent-dim)] transition-colors"
            placeholder="Enter domain, IP, email, URL, username, or organization..."
            autoComplete="off"
            autoFocus
          />
          {/* Detected type chip */}
          {targetValue && detectedType !== "unknown" && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--nx-accent)]/30 bg-[var(--nx-accent-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--nx-accent)]">
                <TypeIcon className="h-3.5 w-3.5" />
                {typeInfo.label}
              </span>
            </div>
          )}
        </div>
        {errors.target && (
          <p className="mt-2 text-sm text-red-400">{errors.target.message}</p>
        )}
        {targetValue && detectedType === "unknown" && (
          <p className="mt-2 text-xs text-[var(--nx-text-muted)]">
            Type not detected — the backend will classify this target automatically.
          </p>
        )}
      </div>

      {/* Investigation name (optional) */}
      <div>
        <label
          htmlFor="name"
          className="block text-xs font-medium uppercase tracking-wider text-[var(--nx-text-tertiary)] mb-2"
        >
          Investigation Name <span className="normal-case tracking-normal text-[var(--nx-text-muted)]">(optional)</span>
        </label>
        <input
          id="name"
          type="text"
          {...register("name")}
          className="block w-full rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-2 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent-dim)] focus:outline-none focus:ring-1 focus:ring-[var(--nx-accent-dim)] transition-colors"
          placeholder="Auto-generated from target if left blank"
        />
      </div>

      {/* Depth selector */}
      <div>
        <label className="block text-xs font-medium uppercase tracking-wider text-[var(--nx-text-tertiary)] mb-3">
          Investigation Depth
        </label>
        <div className="grid grid-cols-3 gap-2">
          {depthOptions.map((opt) => (
            <label
              key={opt.value}
              className={cn(
                "relative flex cursor-pointer flex-col rounded-md border p-3 transition-colors",
                "border-[var(--nx-border)] bg-[var(--nx-surface-3)] hover:border-[var(--nx-border-strong)]",
                "has-[:checked]:border-[var(--nx-accent-dim)] has-[:checked]:bg-[var(--nx-accent-subtle)]",
              )}
            >
              <input
                type="radio"
                value={opt.value}
                {...register("depth")}
                className="sr-only"
              />
              <span className="text-sm font-medium text-[var(--nx-text-primary)]">
                {opt.label}
              </span>
              <span className="mt-1 text-[11px] text-[var(--nx-text-tertiary)] leading-snug">
                {opt.desc}
              </span>
              <span className="mt-1.5 text-[10px] font-mono text-[var(--nx-text-muted)]">
                {opt.time}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Error message */}
      {mutation.isError && (
        <div className="rounded-md border border-red-500/25 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {mutation.error.message}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={mutation.isPending || !targetValue?.trim()}
        className={cn(
          "group inline-flex w-full items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-all",
          "bg-[var(--nx-accent)] text-[var(--nx-base)] hover:brightness-110",
          "disabled:opacity-40 disabled:cursor-not-allowed",
        )}
      >
        {mutation.isPending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Creating Investigation...
          </>
        ) : (
          <>
            Start Investigation
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </>
        )}
      </button>
    </form>
  );
}
