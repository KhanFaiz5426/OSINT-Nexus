import re

with open("frontend/src/pages/SettingsPage.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "Server,\n} from \"lucide-react\";",
    "Server,\n  Key,\n  Database,\n} from \"lucide-react\";"
)

# 2. Add search to AppSettings
search_interface = """  search: {
    searxng_enabled: boolean;
    searxng_base_url: string;
    provider_timeout: number;
    max_results_per_provider: number;
  };
"""
content = re.sub(
    r"(llm: \{[^}]+\};\n)",
    r"\1" + search_interface,
    content
)

# 3. Update Sections
content = re.sub(
    r'type Section = "general" \| "llm" \| "collectors" \| "investigation" \| "system";',
    'type Section = "general" | "llm" | "search" | "credentials" | "collectors" | "investigation" | "system";',
    content
)

new_sections = """const SECTIONS: { key: Section; label: string; icon: React.ElementType }[] = [
  { key: "general", label: "General", icon: Settings },
  { key: "llm", label: "AI / Intelligence", icon: Brain },
  { key: "search", label: "Search", icon: Search },
  { key: "credentials", label: "API Credentials", icon: Key },
  { key: "collectors", label: "Collection", icon: Database },
  { key: "investigation", label: "Investigation", icon: Shield },
  { key: "system", label: "System & Data", icon: Server },
];"""

content = re.sub(
    r"const SECTIONS:[^\]]+\];",
    new_sections,
    content
)

# 4. Add apiKeysUpdate state
content = content.replace(
    "const [hasChanges, setHasChanges] = useState(false);",
    "const [hasChanges, setHasChanges] = useState(false);\n  const [apiKeysUpdate, setApiKeysUpdate] = useState<Record<string, string>>({});"
)

# 5. Clear apiKeysUpdate on save success
content = content.replace(
    "setHasChanges(false);\n      queryClient.invalidateQueries",
    "setHasChanges(false);\n      setApiKeysUpdate({});\n      queryClient.invalidateQueries"
)

# 6. Update handleSave
old_handle_save = """  const handleSave = () => {
    if (!editState) return;
    const update: Partial<AppSettings> = {};
    if (activeSection === "general") update.general = editState.general;
    if (activeSection === "llm") update.llm = editState.llm;
    if (activeSection === "collectors") update.collectors = editState.collectors;
    if (activeSection === "investigation") update.investigation = editState.investigation;
    saveMutation.mutate(update);
  };"""

new_handle_save = """  const handleSave = () => {
    if (!editState) return;
    const update: Partial<AppSettings> & { api_keys?: Record<string, string> } = {};
    if (activeSection === "general") update.general = editState.general;
    if (activeSection === "llm") update.llm = editState.llm;
    if (activeSection === "search") update.search = editState.search;
    if (activeSection === "collectors") update.collectors = editState.collectors;
    if (activeSection === "investigation") update.investigation = editState.investigation;
    if (activeSection === "credentials") {
      if (Object.keys(apiKeysUpdate).length > 0) {
        update.api_keys = apiKeysUpdate;
      } else {
        return;
      }
    }
    saveMutation.mutate(update);
  };"""

content = content.replace(old_handle_save, new_handle_save)

# 7. Update handleReset to reset api keys
content = content.replace(
    "setHasChanges(false);\n    }\n  };",
    "setHasChanges(false);\n      setApiKeysUpdate({});\n    }\n  };"
)

# 8. Render new sections in main content
old_section_render = """          {activeSection === "general" && (
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
          )}"""

new_section_render = """          {activeSection === "general" && (
            <GeneralSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "llm" && (
            <LLMSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "search" && (
            <SearchSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "credentials" && (
            <CredentialsSection 
              apiKeysStatus={data.api_keys} 
              apiKeysUpdate={apiKeysUpdate} 
              onChange={(k, v) => {
                setApiKeysUpdate(p => ({ ...p, [k]: v }));
                setHasChanges(true);
              }} 
            />
          )}
          {activeSection === "collectors" && (
            <CollectorsSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "investigation" && (
            <InvestigationSection settings={editState} onChange={updateField} />
          )}
          {activeSection === "system" && (
            <SystemSection settings={editState} health={data.service_health} />
          )}"""

content = content.replace(old_section_render, new_section_render)

# 9. Modify LLMSection - remove apiKeys prop and API Key Status Card
# Let's replace the entire LLMSection
old_llm_start = "function LLMSection({"
old_llm_end = "/* ── Collectors Section"
llm_chunk = content[content.find(old_llm_start):content.find(old_llm_end)]

new_llm_chunk = """function LLMSection({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (path: string, value: any) => void;
}) {
  const providers = ["ollama", "nvidia", "openai", "anthropic", "opencode", "none"];
  const activeProvider = settings.llm.active_provider;
  const showBaseUrl = activeProvider === "ollama" || !PROVIDER_BASE_URLS[activeProvider];
  // Hide settings if none is selected
  const isNone = activeProvider === "none";

  return (
    <div className="space-y-6">
      <SettingCard title="Active Provider" description="Select the LLM provider for AI-assisted analysis">
        <FormField
          label="Provider"
          hint={isNone ? "" : "Restart required after changing. The provider must have a valid API key configured in API Credentials."}
        >
          <select
            value={settings.llm.active_provider}
            onChange={(e) => onChange("llm.active_provider", e.target.value)}
            className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
          >
            {providers.map((p) => (
              <option key={p} value={p}>
                {p === "none" ? "None (Disable AI)" : p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </FormField>
        
        {!isNone && (
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
                  ? "e.g. llama3.1, gemma4:31b-cloud"
                  : activeProvider === "nvidia"
                    ? "e.g. nvidia/nemotron-3.5-lightning-30b-a3b"
                    : activeProvider === "anthropic"
                      ? "e.g. claude-sonnet-4-20250514"
                      : "e.g. gpt-4o, gpt-4o-mini"
              }
              className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)]"
            />
          </FormField>
        )}
        
        {!isNone && showBaseUrl && (
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

      {!isNone && (
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
      )}
    </div>
  );
}

"""
content = content.replace(llm_chunk, new_llm_chunk)

# 10. Add SearchSection and CredentialsSection before CollectorsSection
new_sections_code = """
/* ── Search Section ─────────────────────────────────────────────────────── */

function SearchSection({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (path: string, value: any) => void;
}) {
  const searchSettings = settings.search || {
    searxng_enabled: true,
    searxng_base_url: "",
    provider_timeout: 10.0,
    max_results_per_provider: 40,
  };

  return (
    <div className="space-y-6">
      <SettingCard title="SearXNG Engine" description="Configure the optional multi-provider meta-search engine">
        <FormField label="Enable SearXNG" hint="When enabled, uses SearXNG for web searches instead of directly using DuckDuckGo. Optional natively.">
          <Toggle
            checked={searchSettings.searxng_enabled}
            onChange={(v) => onChange("search.searxng_enabled", v)}
          />
        </FormField>
        
        {searchSettings.searxng_enabled && (
            <FormField label="SearXNG Base URL" hint="URL to your SearXNG instance (e.g. http://localhost:8088)">
              <input
                type="text"
                value={searchSettings.searxng_base_url}
                onChange={(e) => onChange("search.searxng_base_url", e.target.value)}
                placeholder="http://localhost:8088"
                className="w-full mt-2 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)]"
              />
            </FormField>
        )}
      </SettingCard>

      <SettingCard title="Search Constraints" description="Limits for search execution">
         <FormField label="Provider Timeout" hint="How long to wait (in seconds) for each search provider before giving up.">
          <div className="flex items-center gap-3 mt-2">
            <input
              type="range"
              min={1}
              max={60}
              step={1}
              value={searchSettings.provider_timeout}
              onChange={(e) => onChange("search.provider_timeout", parseFloat(e.target.value))}
              className="flex-1 accent-[var(--nx-accent)]"
            />
            <span className="w-12 text-right text-sm font-mono text-[var(--nx-text-primary)]">
              {searchSettings.provider_timeout.toFixed(1)}s
            </span>
          </div>
          <p className="text-[11px] text-[var(--nx-text-muted)] mt-1">1.0 – 60.0 seconds (default: 10.0)</p>
        </FormField>
        
        <div className="mt-4 pt-4 border-t border-[var(--nx-border)]">
          <InfoRow label="Max Results Per Provider" value={searchSettings.max_results_per_provider.toString()} />
          <p className="text-[11px] text-[var(--nx-text-muted)] mt-1.5">
            The maximum number of search results retrieved per provider is securely locked to {searchSettings.max_results_per_provider} for system stability and analysis quality.
          </p>
        </div>
      </SettingCard>
    </div>
  );
}

/* ── Credentials Section ────────────────────────────────────────────────── */

function CredentialsSection({
  apiKeysStatus,
  apiKeysUpdate,
  onChange,
}: {
  apiKeysStatus: Record<string, boolean>;
  apiKeysUpdate: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  const aiCredentials = [
    { key: "nvidia", label: "NVIDIA API Key" },
    { key: "openai", label: "OpenAI API Key" },
    { key: "anthropic", label: "Anthropic API Key" },
    { key: "opencode", label: "OpenCode API Key" },
  ];
  const osintCredentials = [
    { key: "github", label: "GitHub Token" },
    { key: "abuseipdb", label: "AbuseIPDB Key" },
    { key: "urlhaus", label: "URLhaus Key" },
  ];

  return (
    <div className="space-y-6">
      <SettingCard title="AI Provider Credentials" description="Securely configure API keys for AI providers. Keys are encrypted in the native Windows Credential Manager.">
        <div className="space-y-4">
          {aiCredentials.map(c => (
             <CredentialField 
               key={c.key} 
               label={c.label} 
               configured={apiKeysStatus[c.key]}
               value={apiKeysUpdate[c.key]}
               onChange={(v) => onChange(c.key, v)} 
             />
          ))}
        </div>
      </SettingCard>
      
      <SettingCard title="OSINT API Credentials" description="API keys for specialized data collection sources.">
        <div className="space-y-4">
          {osintCredentials.map(c => (
             <CredentialField 
               key={c.key} 
               label={c.label} 
               configured={apiKeysStatus[c.key]}
               value={apiKeysUpdate[c.key]}
               onChange={(v) => onChange(c.key, v)} 
             />
          ))}
        </div>
      </SettingCard>
    </div>
  );
}

function CredentialField({ label, configured, value, onChange }: { label: string, configured: boolean, value?: string, onChange: (v: string) => void }) {
  const willClear = value === "";
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-[var(--nx-text-secondary)]">{label}</label>
        {configured && value === undefined && (
           <div className="flex items-center gap-2">
             <span className="text-[10px] text-emerald-400 font-medium bg-emerald-400/10 px-1.5 py-0.5 rounded">Configured</span>
             <button onClick={() => onChange("")} className="text-[10px] text-red-400 hover:underline">Clear</button>
           </div>
        )}
        {willClear && (
           <span className="text-[10px] text-red-400 font-medium bg-red-400/10 px-1.5 py-0.5 rounded">Will be cleared on save</span>
        )}
      </div>
      <input
        type="password"
        value={value === undefined ? "" : value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={configured && !willClear ? "•••••••••••••••• (Set new key to replace)" : "Enter API key"}
        className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-1.5 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:outline-none focus:border-[var(--nx-accent)] transition-colors"
      />
    </div>
  );
}

"""
content = content.replace("/* ── Collectors Section", new_sections_code + "\n/* ── Collectors Section")

with open("frontend/src/pages/SettingsPage.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("Patching complete.")
