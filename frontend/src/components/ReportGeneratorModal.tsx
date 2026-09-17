import { useState } from "react";
import { X, FileDown, Check, Loader2, FileText, File } from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { useGenerateReport } from "../hooks/useApi";
import { reportsApi, type ReportFormat } from "../api/investigations";
import { workspaceApi } from "../api/workspace";
import { cn } from "../lib/utils";

export function ReportGeneratorModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [scope, setScope] = useState<"investigation" | "workspace">("investigation");
  const [generatingFormat, setGeneratingFormat] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const activeTabId = useWorkspaceStore((s) => s.activeTabId);

  const generateInvReport = useGenerateReport();

  if (!open) return null;

  const handleGenerate = async (format: ReportFormat) => {
    setGeneratingFormat(format);
    setLastSuccess(null);
    setErrorMsg(null);

    try {
      let downloadUrl = "";
      let ext = format;

      if (scope === "investigation") {
        if (!activeTabId) {
          throw new Error("No active investigation selected.");
        }
        const report = await generateInvReport.mutateAsync({
          investigationId: activeTabId,
          format,
        });
        ext = report.format || format;
        downloadUrl = reportsApi.downloadUrl(activeTabId, report.id);
      } else {
        const report = await workspaceApi.generateReport(format);
        ext = report.format || format;
        downloadUrl = workspaceApi.downloadReportUrl(report.id);
      }

      const filename = scope === "workspace" ? `workspace_report.${ext}` : `report.${ext}`;

      // @ts-ignore - pywebview is injected by the desktop shell
      if (window.pywebview && window.pywebview.api && window.pywebview.api.save_report_dialog) {
        // Desktop Mode: native file save
        // @ts-ignore
        const savePath = await window.pywebview.api.save_report_dialog(filename, ext);
        if (savePath) {
          const fullUrl = window.location.origin + downloadUrl;
          // @ts-ignore
          const success = await window.pywebview.api.download_file_to_path(fullUrl, savePath);
          if (!success) {
            throw new Error(`Failed to save report to disk.`);
          }
        }
      } else {
        // Browser Mode: standard blob download
        const res = await fetch(downloadUrl);
        if (!res.ok) throw new Error("Failed to download file from server");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }

      setLastSuccess(ext);
      setTimeout(() => {
        setLastSuccess(null);
        onClose();
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate report");
    } finally {
      setGeneratingFormat(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-[450px] overflow-hidden rounded-xl border border-[var(--nx-border)] bg-[var(--nx-surface-1)] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-4 py-3">
          <div className="flex items-center gap-2">
            <FileDown className="h-5 w-5 text-[var(--nx-accent)]" />
            <h2 className="text-sm font-semibold text-[var(--nx-text-primary)]">
              Generate Report
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          <div className="mb-4">
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
              Report Scope
            </label>
            <div className="flex flex-col gap-1.5">
              <label
                className={cn(
                  "flex items-center gap-3 rounded border p-2.5 cursor-pointer transition-colors",
                  scope === "investigation"
                    ? "border-[var(--nx-accent)] bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]"
                    : "border-[var(--nx-border)] bg-[var(--nx-surface-2)] text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)]"
                )}
              >
                <input
                  type="radio"
                  name="reportScope"
                  className="hidden"
                  checked={scope === "investigation"}
                  onChange={() => setScope("investigation")}
                />
                <File className="h-4 w-4 shrink-0" />
                <div className="flex flex-col">
                  <span className="text-xs font-medium">Investigation Report</span>
                  <span className="text-[10px] opacity-80">Detailed intelligence report for the active investigation</span>
                </div>
              </label>

              <label
                className={cn(
                  "flex items-center gap-3 rounded border p-2.5 cursor-pointer transition-colors",
                  scope === "workspace"
                    ? "border-amber-500 bg-amber-500/10 text-amber-500"
                    : "border-[var(--nx-border)] bg-[var(--nx-surface-2)] text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)]"
                )}
              >
                <input
                  type="radio"
                  name="reportScope"
                  className="hidden"
                  checked={scope === "workspace"}
                  onChange={() => setScope("workspace")}
                />
                <FileText className="h-4 w-4 shrink-0" />
                <div className="flex flex-col">
                  <span className="text-xs font-medium">Workspace Report</span>
                  <span className="text-[10px] opacity-80">Intelligence overview across the entire workspace</span>
                </div>
              </label>
            </div>
          </div>

          {scope === "investigation" && !activeTabId && (
            <div className="mb-4 rounded-md bg-amber-500/10 p-3 text-xs text-amber-500 border border-amber-500/20">
              No active investigation selected. Please open an investigation tab to generate this report.
            </div>
          )}

          {errorMsg && (
            <div className="mb-4 rounded-md bg-red-500/10 p-3 text-xs text-red-500 border border-red-500/20">
              {errorMsg}
            </div>
          )}

          <div className="mt-5 pt-4 border-t border-[var(--nx-border)] flex gap-2 justify-end">
            <button
              onClick={() => handleGenerate("html")}
              disabled={generatingFormat !== null || (scope === "investigation" && !activeTabId)}
              className="inline-flex items-center justify-center gap-1.5 rounded bg-[var(--nx-accent)] px-3 py-1.5 text-xs font-medium text-[var(--nx-base)] hover:brightness-110 active:scale-95 transition-all disabled:opacity-50 disabled:pointer-events-none"
            >
              {generatingFormat === "html" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : lastSuccess === "html" ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <FileText className="h-3.5 w-3.5" />
              )}
              Generate HTML Report
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
