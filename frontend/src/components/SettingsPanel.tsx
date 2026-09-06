import { useQuery } from "@tanstack/react-query";

interface CollectorStatus {
  name: string;
  version: string;
  available: boolean;
  api_key_configured: boolean;
  requires_api_key: boolean;
  supported_target_types: string[];
}

interface LLMProviderStatus {
  name: string;
  configured: boolean;
  selected: boolean;
}

interface ConfigStatus {
  app_version: string;
  llm_provider: string;
  llm_configured: boolean;
  collectors: CollectorStatus[];
  llm_providers: LLMProviderStatus[];
}

async function fetchConfigStatus(): Promise<ConfigStatus> {
  const res = await fetch("/api/v1/config/status");
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs rounded ${
        ok
          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
          : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
      }`}
    >
      {ok ? "Configured" : "Not configured"}
    </span>
  );
}

export default function SettingsPanel() {
  const { data: config, isLoading, error } = useQuery({
    queryKey: ["config-status"],
    queryFn: fetchConfigStatus,
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-gray-500 dark:text-gray-400">
        Loading configuration...
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="p-4 text-sm text-red-500">
        Failed to load configuration status.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6 overflow-y-auto max-h-[600px]">
      <div>
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
          System
        </h3>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Version: {config.app_version}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
          LLM Provider
        </h3>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500 dark:text-gray-400 w-24">Active:</span>
            <span className="font-mono text-gray-900 dark:text-gray-100">
              {config.llm_provider}
            </span>
            <StatusBadge ok={config.llm_configured} />
          </div>
          <div className="mt-2 space-y-1">
            {config.llm_providers.map((p) => (
              <div
                key={p.name}
                className="flex items-center gap-2 text-xs"
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    p.selected
                      ? "bg-blue-500"
                      : "bg-gray-300 dark:bg-gray-600"
                  }`}
                />
                <span className="w-20 text-gray-700 dark:text-gray-300">
                  {p.name}
                </span>
                <StatusBadge ok={p.configured} />
                {p.selected && (
                  <span className="text-[10px] text-blue-600 dark:text-blue-400">
                    (selected)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
          OSINT Collectors
        </h3>
        <div className="space-y-1.5">
          {config.collectors.map((c) => (
            <div
              key={c.name}
              className="flex items-center gap-2 text-xs"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  c.available
                    ? "bg-green-500"
                    : "bg-red-500"
                }`}
              />
              <span className="w-28 text-gray-700 dark:text-gray-300 font-mono">
                {c.name}
              </span>
              {c.requires_api_key ? (
                <StatusBadge ok={c.api_key_configured} />
              ) : (
                <span className="text-[10px] text-gray-400">no key needed</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
