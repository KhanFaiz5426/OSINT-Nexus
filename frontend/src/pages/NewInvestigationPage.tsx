import { Link } from "react-router-dom";
import { InvestigationForm } from "../components/InvestigationForm";
import { Crosshair, ArrowLeft } from "lucide-react";

export function NewInvestigationPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Back link */}
        <Link
          to="/investigations"
          className="mb-8 inline-flex items-center gap-1.5 text-xs text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)] transition-colors"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to Investigations
        </Link>

        {/* Logo and heading */}
        <div className="mb-10 text-center">
          <div className="mb-4 flex items-center justify-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--nx-accent-subtle)] border border-[var(--nx-accent)]/20">
              <Crosshair className="h-6 w-6 text-[var(--nx-accent)]" />
            </div>
          </div>
          <h1 className="text-2xl font-semibold text-[var(--nx-text-primary)]">
            New Investigation
          </h1>
          <p className="mt-2 text-sm text-[var(--nx-text-tertiary)]">
            Enter a target to begin collecting and correlating OSINT data.
          </p>
        </div>

        {/* Form */}
        <InvestigationForm />
      </div>
    </div>
  );
}
