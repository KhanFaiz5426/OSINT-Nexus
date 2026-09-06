import { useState } from "react";
import {
  FileText,
  FileJson,
  FileSpreadsheet,
  Download,
  Loader2,
  Check,
  File,
} from "lucide-react";
import {
  useReports,
  useGenerateReport,
  type ReportFormat,
} from "../hooks/useApi";
import { reportsApi } from "../api/investigations";

interface ReportsPanelProps {
  investigationId: string;
}

const FORMAT_OPTIONS: { value: ReportFormat; label: string; icon: typeof FileText }[] = [
  { value: "html", label: "HTML", icon: FileText },
  { value: "pdf", label: "PDF", icon: File },
  { value: "json", label: "JSON", icon: FileJson },
  { value: "csv", label: "CSV", icon: FileSpreadsheet },
];

const FORMAT_COLORS: Record<ReportFormat, string> = {
  html: "bg-sky-500/15 text-sky-400",
  pdf: "bg-red-500/15 text-red-400",
  json: "bg-emerald-500/15 text-emerald-400",
  csv: "bg-purple-500/15 text-purple-400",
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function ReportsPanel({ investigationId }: ReportsPanelProps) {
  const reports = useReports(investigationId);
  const generateReport = useGenerateReport();
  const [generatingFormat, setGeneratingFormat] = useState<string | null>(null);

  const handleGenerate = async (format: ReportFormat) => {
    setGeneratingFormat(format);
    try {
      await generateReport.mutateAsync({ investigationId, format });
    } finally {
      setGeneratingFormat(null);
    }
  };

  return (
    <div className="flex h-full flex-col rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)]">
      <div className="flex items-center justify-between border-b border-[var(--nx-border)] px-4 py-2.5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-secondary)]">
          Reports & Export
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-4">
          <p className="mb-3 text-[11px] text-[var(--nx-text-muted)]">
            Generate reports with full evidence attribution and source provenance.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {FORMAT_OPTIONS.map(({ value, label, icon: Icon }) => {
              const isGenerating = generatingFormat === value;
              return (
                <button
                  key={value}
                  onClick={() => handleGenerate(value)}
                  disabled={isGenerating}
                  className="flex items-center gap-2 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-2 text-xs font-medium text-[var(--nx-text-secondary)] transition-colors hover:bg-[var(--nx-surface-4)] disabled:opacity-50"
                >
                  {isGenerating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--nx-text-muted)]" />
                  ) : (
                    <Icon className="h-3.5 w-3.5 text-[var(--nx-text-tertiary)]" />
                  )}
                  {label}
                </button>
              );
            })}
          </div>
          {generateReport.isError && (
            <p className="mt-2 text-xs text-red-400">
              {generateReport.error.message}
            </p>
          )}
          {generateReport.isSuccess && (
            <p className="mt-2 flex items-center gap-1 text-xs text-emerald-400">
              <Check className="h-3 w-3" /> Report generated
            </p>
          )}
        </div>

        <div>
          <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
            Generated Reports
          </h4>
          {reports.isLoading && (
            <p className="text-xs text-[var(--nx-text-muted)]">Loading...</p>
          )}
          {reports.data && reports.data.length === 0 && (
            <p className="text-xs text-[var(--nx-text-muted)]">No reports generated yet.</p>
          )}
          {reports.data && reports.data.length > 0 && (
            <div className="space-y-2">
              {reports.data.map((report) => (
                <div
                  key={report.id}
                  className="flex items-center justify-between rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${FORMAT_COLORS[report.format]}`}
                    >
                      {report.format}
                    </span>
                    <span className="text-xs font-mono text-[var(--nx-text-muted)]">
                      {formatBytes(report.file_size)}
                    </span>
                  </div>
                  <a
                    href={reportsApi.downloadUrl(investigationId, report.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors"
                  >
                    <Download className="h-3 w-3" />
                    Download
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
