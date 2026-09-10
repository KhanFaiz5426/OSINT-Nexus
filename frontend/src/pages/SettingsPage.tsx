import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Save,
  RotateCcw,
  Check,
  X,
  Brain,
  Search,
  Settings,
  Shield,
  ChevronRight,
  Loader2,
  Server,
} from "lucide-react";
import { cn } from "../lib/utils";

const API = "/api/v1";

interface AppSettings {
  general: {
    default_depth: string;
    max_concurrent_investigations: number;
    auto_save_reports: boolean;
  };
  llm: {
    active_provider: string;
    model: string;
    base_url: string;
    max_tokens: number;
    temperature: number;
    api_keys_configured: Record<string, boolean>;
  };
  collectors: {
    enabled: Record<string, boolean>;
    rate_limits: Record<string, number>;
    cache_ttl: number;
    search_rate_limit_rpm: number;
  };
  investigation: {
    api_budget: number;
    probe: {
      max_variations: number;
      max_platforms: number;
      max_total_requests: number;
      timeout: number;
    };
  };
  version: string;
}

interface SettingsResponse {
  settings: AppSettings;
  api_keys: Record<string, boolean>;
  service_health: Record<string, any>;
  restart_required: string[];
}

interface SettingsUpdateResponse {
  message: string;
  settings: AppSettings;
  restart_required: string[];
}

type Section = "general" | "llm" | "collectors" | "investigation" | "system";

const SECTIONS: { key: Section; label: string; icon: React.ElementType }[] = [
  { key: "general", label: "General", icon: Settings },
  { key: "llm", label: "AI / Providers", icon: Brain },
  { key: "collectors", label: "OSINT / Collectors", icon: Search },
  { key: "investigation", label: "Investigation", icon: Shield },
  { key: "system", label: "System & Data", icon: Server },
];

const PROVIDER_BASE_URLS: Record<string, string> = {
  ollama: "http://localhost:11434",
  nvidia: "https://integrate.api.nvidia.com/v1",
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com",
  opencode: "https://opencode.ai/zen/v1",
};

const COLLECTOR_LABELS: Record<string, { label: string; description: string }> = {
  dns: { label: "DNS", description: "A, AAAA, MX, NS, TXT, SOA, CAA records" },
  whois: { label: "WHOIS / RDAP", description: "Domain registration data" },
  certificate_transparency: { label: "Certificate Transparency", description: "SSL/TLS certificate history via crt.sh" },
  ip_to_asn: { label: "IP to ASN", description: "Autonomous system number mapping" },
  github: { label: "GitHub", description: "User profiles, repos, and commits" },
  http: { label: "HTTP / Headers", description: "HTTP headers, technologies, redirects" },
  threat_intel: { label: "Threat Intelligence", description: "AbuseIPDB and URLhaus lookups" },
  reddit: { label: "Reddit", description: "User profiles and posts" },
  keybase: { label: "Keybase", description: "Keybase user proofs" },
  hackernews: { label: "Hacker News", description: "User profiles and submissions" },
  gitlab: { label: "GitLab", description: "User profiles and projects" },
  search: { label: "Web Search", description: "Multi-provider search engine queries" },
};

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeSection, setActiveSection] = useState<Section>("general");
  const [editState, setEditState] = useState<AppSettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
    restartRequired?: string[];
  } | null>(null);

  const { data, isLoading, error } = useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: () => fetch(`${API}/settings`).then((r) => r.json()),
    staleTime: 60000,
  });

  const saveMutation = useMutation({
    mutationFn: (update: Partial<AppSettings>) =>
      fetch(`${API}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      }).then((r) => {
        if (!r.ok) throw new Error("Failed to save");
        return r.json() as Promise<SettingsUpdateResponse>;
      }),
    onSuccess: (resp) => {
      setSaveMessage({
        type: "success",
        text: resp.message,
        restartRequired: resp.restart_required,
      });
      setHasChanges(false);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setTimeout(() => setSaveMessage(null), 5000);
    },
    onError: () => {
      setSaveMessage({ type: "error", text: "Failed to save settings" });
      setTimeout(() => setSaveMessage(null), 5000);
    },
  });

  useEffect(() => {
    if (data?.settings) {
      setEditState(structuredClone(data.settings));
    }
  }, [data]);

  const handleSave = () => {
    if (!editState) return;
    const update: Partial<AppSettings> = {};
    if (activeSection === "general") update.general = editState.general;
    if (activeSection === "llm") update.llm = editState.llm;
    if (activeSection === "collectors") update.collectors = editState.collectors;
    if (activeSection === "investigation") update.investigation = editState.investigation;
    saveMutation.mutate(update);
  };

  const handleReset = () => {
    if (data?.settings) {
      setEditState(structuredClone(data.settings));
      setHasChanges(false);
    }
  };

  const updateField = (path: string, value: any) => {
    if (!editState) return;
    const cloned = structuredClone(editState);
    const keys = path.split(".");
    let obj: any = cloned;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]];
    }
    obj[keys[keys.length - 1]] = value;
    setEditState(cloned);
    setHasChanges(true);
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-[var(--nx-base)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--nx-accent)]" />
      </div>
    );
  }

  if (error || !data || !editState) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[var(--nx-base)]">
        <p className="text-sm text-[var(--nx-text-secondary)]">Failed to load settings</p>
        <Link
          to="/"
          className="flex items-center gap-1.5 text-xs text-[var(--nx-accent)] hover:underline"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to Workstation
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-[var(--nx-base)]">
      {/* Left sidebar navigation */}
      <div className="w-56 shrink-0 border-r border-[var(--nx-border)] bg-[var(--nx-surface-1)]">
        <div className="border-b border-[var(--nx-border)] px-4 py-3">
          <Link
            to="/"
            className="mb-2 flex items-center gap-1.5 text-[11px] text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)] transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to Workstation
          </Link>
          <h1 className="text-sm font-semibold text-[var(--nx-text-primary)]">Settings</h1>
        </div>
        <nav className="p-2">
          {SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.key}
                onClick={() => setActiveSection(section.key)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                  activeSection === section.key
                    ? "bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)]",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{section.label}</span>
                <ChevronRight className="ml-auto h-3 w-3 opacity-40" />
              </button>
            );
          })}
        </nav>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header bar */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--nx-border)] px-6">
          <h2 className="text-sm font-medium text-[var(--nx-text-primary)]">
            {SECTIONS.find((s) => s.key === activeSection)?.label}
          </h2>
          <div className="flex items-center gap-2">
            {saveMessage && (
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded px-2 py-1 text-xs",
                  saveMessage.type === "success"
                    ? "bg-green-500/10 text-green-400"
                    : "bg-red-500/10 text-red-400",
                )}
              >
                {saveMessage.type === "success" ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <X className="h-3 w-3" />
                )}
                {saveMessage.text}
              </div>
            )}
            {hasChanges && (
              <>
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1.5 rounded border border-[var(--nx-border)] px-3 py-1.5 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)]"
                >
                  <RotateCcw className="h-3 w-3" />
                  Reset
                </button>
                <button
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-1.5 rounded bg-[var(--nx-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--nx-accent)]/90 disabled:opacity-50"
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Save className="h-3 w-3" />
                  )}
                  Save
                </button>
              </>
            )}
          </div>
        </div>

        {/* Section content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeSection === "general" && (
            <GeneralSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "llm" && (
            <LLMSection settings={editState} apiKeys={data.api_keys} onChange={updateField} />
          )}
          {activeSection === "collectors" && (
            <CollectorsSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "investigation" && (
            <InvestigationSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "system" && (
            <SystemSection settings={editState} health={data.service_health} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ── General Section ────────────────────────────────────────────────────── */

function GeneralSection({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (path: string, value: any) => void;
}) {
  return (
    <div className="space-y-6">
      <SettingCard
        title="Investigation Defaults"
        description="Default behavior applied to new investigations"
      >
        <FormField
          label="Default Depth"
          hint="How deeply new investigations collect data. Shallow is fast; deep explores more sources."
        >
          <select
            value={settings.general.default_depth}
            onChange={(e) => onChange("general.default_depth", e.target.value)}
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
          >
            <option value="shallow">Shallow (1 pivot round, fastest)</option>
            <option value="standard">Standard (3 pivot rounds, balanced)</option>
            <option value="deep">Deep (6 pivot rounds, most thorough)</option>
          </select>
        </FormField>
        <FormField
          label="Max Concurrent Investigations"
          hint="How many investigations can run simultaneously. Each running investigation uses its own resources."
        >
          <input
            type="number"
            min={1}
            max={10}
            step={1}
            value={settings.general.max_concurrent_investigations}
            onChange={(e) => {
              const v = parseInt(e.target.value) || 5;
              onChange("general.max_concurrent_investigations", Math.max(1, Math.min(10, v)));
            }}
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
          />
        </FormField>
        <FormField
          label="Auto-save Reports"
          hint="Automatically generate and save a report when an investigation completes."
        >
          <Toggle
            checked={settings.general.auto_save_reports}
            onChange={(v) => onChange("general.auto_save_reports", v)}
          />
        </FormField>
      </SettingCard>
    </div>
  );
}

/* ── LLM Section ───────────────────────────────────────────────────────── */

function LLMSection({
  settings,
  apiKeys,
  onChange,
}: {
  settings: AppSettings;
  apiKeys: Record<string, boolean>;
  onChange: (path: string, value: any) => void;
}) {
  const providers = ["ollama", "nvidia", "openai", "anthropic", "opencode"];
  const activeProvider = settings.llm.active_provider;
  const showBaseUrl = activeProvider === "ollama" || !PROVIDER_BASE_URLS[activeProvider];

  return (
    <div className="space-y-6">
      <SettingCard title="Active Provider" description="Select the LLM provider for AI-assisted analysis">
        <FormField
          label="Provider"
          hint="Restart required after changing. The provider must have a valid API key configured."
        >
          <select
            value={settings.llm.active_provider}
            onChange={(e) => onChange("llm.active_provider", e.target.value)}
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
          >
            {providers.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
                {apiKeys[p] ? " — key configured" : " — no key"}
              </option>
            ))}
          </select>
        </FormField>
        <FormField
          label="Model"
          hint="The specific model to use. Leave empty to use the provider's default."
        >
          <input
            type="text"
            value={settings.llm.model}
            onChange={(e) => onChange("llm.model", e.target.value)}
            placeholder={
              activeProvider === "ollama"
                ? "e.g. llama3.1, mistral, codellama"
                : activeProvider === "nvidia"
                  ? "e.g. nvidia/nemotron-3.5-lightning-30b-a3b"
                  : activeProvider === "anthropic"
                    ? "e.g. claude-sonnet-4-20250514"
                    : "e.g. gpt-4o, gpt-4o-mini"
            }
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)]"
          />
        </FormField>
        {showBaseUrl && (
          <FormField
            label="Base URL"
            hint="API endpoint URL. Pre-filled for known providers. Change only for custom/local endpoints."
          >
            <input
              type="text"
              value={settings.llm.base_url}
              onChange={(e) => onChange("llm.base_url", e.target.value)}
              placeholder={PROVIDER_BASE_URLS[activeProvider] || "https://api.example.com/v1"}
              className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)]"
            />
          </FormField>
        )}
      </SettingCard>

      <SettingCard title="Generation Parameters" description="Controls for LLM output length and creativity">
        <FormField
          label="Max Tokens"
          hint="Maximum number of tokens the model can generate in a single response. Higher values allow longer outputs but cost more."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={256}
              max={16384}
              step={256}
              value={settings.llm.max_tokens}
              onChange={(e) => onChange("llm.max_tokens", parseInt(e.target.value))}
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-16 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.llm.max_tokens.toLocaleString()}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">256 – 16,384 tokens (default: 2,048)</p>
        </FormField>
        <FormField
          label="Temperature"
          hint="Controls randomness. Lower = more focused and deterministic. Higher = more creative and varied."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={settings.llm.temperature}
              onChange={(e) => onChange("llm.temperature", parseFloat(e.target.value))}
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.llm.temperature.toFixed(2)}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">0.00 (deterministic) – 2.00 (creative, default: 0.30)</p>
        </FormField>
      </SettingCard>

      <SettingCard title="API Key Status" description="Keys are managed via environment variables for security">
        <div className="space-y-1.5">
          {Object.entries(apiKeys).map(([provider, configured]) => (
            <div
              key={provider}
              className="flex items-center justify-between rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2"
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    configured ? "bg-emerald-400" : "bg-[var(--nx-text-muted)]",
                  )}
                />
                <span className="text-sm text-[var(--nx-text-primary)] capitalize">{provider}</span>
              </div>
              <span className="text-xs text-[var(--nx-text-muted)]">
                {configured ? "Key configured" : "No key set"}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-md bg-[var(--nx-surface-2)] border border-[var(--nx-border)] px-3 py-2">
          <p className="text-xs text-[var(--nx-text-muted)] leading-relaxed">
            API keys are set via environment variables (<code className="text-[var(--nx-accent)]">.env</code> file) and are never stored in the settings file. After changing keys, restart the backend for changes to take effect.
          </p>
        </div>
      </SettingCard>
    </div>
  );
}

/* ── Collectors Section ─────────────────────────────────────────────────── */

function CollectorsSection({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (path: string, value: any) => void;
}) {
  return (
    <div className="space-y-6">
      <SettingCard
        title="OSINT Collectors"
        description="Enable or disable individual data collection sources"
      >
        <p className="text-xs text-[var(--nx-text-muted)] -mt-2 mb-2">
          Disabled collectors will not run during investigations. Changes take effect on the next investigation start.
        </p>
        <div className="space-y-1">
          {Object.entries(COLLECTOR_LABELS).map(([name, info]) => (
            <div
              key={name}
              className="flex items-center justify-between rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2.5"
            >
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium text-[var(--nx-text-primary)]">
                  {info.label}
                </span>
                <p className="text-[11px] text-[var(--nx-text-muted)] truncate">{info.description}</p>
              </div>
              <div className="ml-3 shrink-0">
                <Toggle
                  checked={settings.collectors.enabled[name] !== false}
                  onChange={(v) => onChange(`collectors.enabled.${name}`, v)}
                />
              </div>
            </div>
          ))}
        </div>
      </SettingCard>

      <SettingCard title="Caching & Rate Limits" description="Global limits applied across all collectors">
        <FormField
          label="Cache Duration"
          hint="How long collected data is reused before re-fetching. Longer = faster but may miss updates."
        >
          <select
            value={settings.collectors.cache_ttl}
            onChange={(e) => onChange("collectors.cache_ttl", parseInt(e.target.value))}
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
          >
            <option value={300}>5 minutes</option>
            <option value={1800}>30 minutes</option>
            <option value={3600}>1 hour</option>
            <option value={14400}>4 hours</option>
            <option value={43200}>12 hours</option>
            <option value={86400}>24 hours (default)</option>
            <option value={259200}>3 days</option>
            <option value={604800}>7 days</option>
          </select>
        </FormField>
        <FormField
          label="Search Rate Limit"
          hint="Maximum search engine queries per minute. Lower values reduce the chance of being rate-limited."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={30}
              step={1}
              value={settings.collectors.search_rate_limit_rpm}
              onChange={(e) =>
                onChange("collectors.search_rate_limit_rpm", parseInt(e.target.value))
              }
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.collectors.search_rate_limit_rpm}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">1 – 30 queries per minute (default: 10)</p>
        </FormField>
      </SettingCard>
    </div>
  );
}

/* ── Investigation Section ──────────────────────────────────────────────── */

function InvestigationSection({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (path: string, value: any) => void;
}) {
  return (
    <div className="space-y-6">
      <SettingCard
        title="API Budget"
        description="Default cost limit for new investigations"
      >
        <FormField
          label="Default Budget"
          hint="Maximum number of external API calls per investigation. Each collector dispatch costs 1 call. When the budget is exhausted, the investigation stops."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={10}
              max={500}
              step={10}
              value={settings.investigation.api_budget}
              onChange={(e) => onChange("investigation.api_budget", parseInt(e.target.value))}
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.investigation.api_budget}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">10 – 500 calls (default: 100). Each call queries one OSINT source.</p>
        </FormField>
      </SettingCard>

      <SettingCard
        title="Username Probe Engine"
        description="Controls for cross-platform username discovery"
      >
        <p className="text-xs text-[var(--nx-text-muted)] -mt-2 mb-2">
          When investigating a username, the probe engine checks multiple platforms and generates name variations. Higher values find more accounts but take longer.
        </p>
        <FormField
          label="Max Name Variations"
          hint="Number of username variations to generate and search (e.g. johndoe, john-doe, j.doe)."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={25}
              step={1}
              value={settings.investigation.probe.max_variations}
              onChange={(e) =>
                onChange("investigation.probe.max_variations", parseInt(e.target.value))
              }
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-8 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.investigation.probe.max_variations}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">1 – 25 variations (default: 10)</p>
        </FormField>
        <FormField
          label="Max Platforms"
          hint="How many platforms to check directly (GitHub, Reddit, etc.)."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={50}
              step={1}
              value={settings.investigation.probe.max_platforms}
              onChange={(e) =>
                onChange("investigation.probe.max_platforms", parseInt(e.target.value))
              }
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-8 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.investigation.probe.max_platforms}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">1 – 50 platforms (default: 20)</p>
        </FormField>
        <FormField
          label="Max HTTP Requests"
          hint="Total HTTP requests the probe engine can make. Limits overall network usage."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={10}
              max={1000}
              step={10}
              value={settings.investigation.probe.max_total_requests}
              onChange={(e) =>
                onChange("investigation.probe.max_total_requests", parseInt(e.target.value))
              }
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.investigation.probe.max_total_requests}
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">10 – 1,000 requests (default: 200)</p>
        </FormField>
        <FormField
          label="Request Timeout"
          hint="How long to wait for each HTTP response before giving up."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={30}
              step={0.5}
              value={settings.investigation.probe.timeout}
              onChange={(e) =>
                onChange("investigation.probe.timeout", parseFloat(e.target.value))
              }
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {settings.investigation.probe.timeout.toFixed(1)}s
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)]">1.0 – 30.0 seconds (default: 5.0)</p>
        </FormField>
      </SettingCard>
    </div>
  );
}

/* ── System & Data Section ─────────────────────────────────────────────── */

function SystemSection({
  settings,
  health,
}: {
  settings: AppSettings;
  health: Record<string, any>;
}) {
  return (
    <div className="space-y-6">
      <SettingCard title="Application" description="OSINT Nexus version and runtime information">
        <InfoRow label="Version" value={`v${settings.version}`} />
        <InfoRow label="Active LLM Provider" value={settings.llm.active_provider} />
        <InfoRow label="Default Investigation Depth" value={settings.general.default_depth} />
        <InfoRow
          label="Enabled Collectors"
          value={
            Object.entries(settings.collectors.enabled)
              .filter(([, v]) => v !== false)
              .map(([k]) => k.replace(/_/g, " "))
              .join(", ") || "All enabled"
          }
        />
      </SettingCard>

      <SettingCard title="Services" description="Backend service connectivity">
        <div className="space-y-1.5">
          <ServiceStatus
            name="PostgreSQL"
            status={health.database ? "connected" : "unavailable"}
            detail={health.database ? `${health.database.host}:${health.database.port}` : ""}
          />
          <ServiceStatus
            name="Neo4j"
            status={health.neo4j ? "connected" : "unavailable"}
            detail={health.neo4j?.uri || ""}
          />
          <ServiceStatus
            name="Redis"
            status={health.redis ? "connected" : "unavailable"}
            detail={health.redis ? `${health.redis.host}:${health.redis.port}` : ""}
          />
        </div>
      </SettingCard>

      <SettingCard title="About" description="OSINT Nexus">
        <p className="text-sm text-[var(--nx-text-secondary)] leading-relaxed">
          OSINT Nexus is an AI-assisted OSINT investigation and correlation framework.
          It automatically collects publicly available information from open sources,
          normalizes data into a unified entity model, and uses AI to suggest investigation pivots.
        </p>
        <div className="mt-3 space-y-1.5">
          <InfoRow label="License" value="Academic / Research Use" />
          <InfoRow label="Version" value={`v${settings.version}`} />
        </div>
        <div className="mt-3 rounded-md bg-[var(--nx-surface-2)] border border-[var(--nx-border)] px-3 py-2">
          <p className="text-[11px] text-[var(--nx-text-muted)] leading-relaxed">
            Built with FastAPI, React, PostgreSQL, Neo4j, Redis, and TanStack Query.
            LLM integration supports NVIDIA, OpenAI, Anthropic, Ollama, and OpenCode providers.
          </p>
        </div>
      </SettingCard>
    </div>
  );
}

/* ── Shared Components ──────────────────────────────────────────────────── */

function SettingCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--nx-border)] bg-[var(--nx-surface-1)]">
      <div className="border-b border-[var(--nx-border)] px-4 py-3">
        <h3 className="text-sm font-medium text-[var(--nx-text-primary)]">{title}</h3>
        <p className="text-xs text-[var(--nx-text-muted)] mt-0.5">{description}</p>
      </div>
      <div className="p-4 space-y-4">{children}</div>
    </div>
  );
}

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--nx-text-secondary)] mb-1">
        {label}
      </label>
      {children}
      {hint && (
        <p className="mt-1 text-[11px] text-[var(--nx-text-muted)] leading-relaxed">{hint}</p>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2">
      <span className="text-xs text-[var(--nx-text-muted)]">{label}</span>
      <span className="text-sm font-mono text-[var(--nx-text-primary)]">{value}</span>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
        checked ? "bg-[var(--nx-accent)]" : "bg-[var(--nx-surface-3)]",
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  );
}

function ServiceStatus({
  name,
  status,
  detail,
}: {
  name: string;
  status: "connected" | "unavailable";
  detail: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            status === "connected" ? "bg-emerald-400" : "bg-red-400",
          )}
        />
        <span className="text-sm text-[var(--nx-text-primary)]">{name}</span>
      </div>
      <div className="text-right">
        <span className="text-xs text-[var(--nx-text-muted)]">
          {status === "connected" ? "Connected" : "Unavailable"}
        </span>
        {detail && (
          <p className="text-[10px] font-mono text-[var(--nx-text-muted)]">{detail}</p>
        )}
      </div>
    </div>
  );
}
