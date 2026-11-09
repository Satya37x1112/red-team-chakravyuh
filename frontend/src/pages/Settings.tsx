import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Empty, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import type { LlmConfig, LlmTestResult } from "../types";

/**
 * Settings — generic LLM provider configuration for the ONE centralized planner.
 * The API key is write-only: it is never returned by the backend, never shown,
 * and only sent when a new value is entered. Runtime changes are non-persistent
 * (set LLM_* / OPENROUTER_* in backend .env for durability). A "Test connection"
 * runs a real harmless inference and shows staged, sanitized results — a green
 * state means an actual inference succeeded, not merely that fields are filled.
 */
export function Settings() {
  const [cfg, setCfg] = useState<LlmConfig | null>(null);
  const [provider, setProvider] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [timeout, setTimeoutS] = useState(60);
  const [apiKey, setApiKey] = useState(""); // write-only; never pre-filled
  const [test, setTest] = useState<LlmTestResult | null>(null);
  const [busy, setBusy] = useState<"" | "save" | "test">("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .llmConfig()
      .then((c) => {
        setCfg(c);
        setProvider(c.provider);
        setBaseUrl(c.base_url ?? "");
        setModel(c.model ?? "");
        setTimeoutS(c.timeout);
      })
      .catch((e) => setMsg(String((e as Error).message)));
  }, []);
  useEffect(() => load(), [load]);

  const save = async () => {
    setBusy("save");
    setMsg(null);
    try {
      const body: Record<string, unknown> = { provider, base_url: baseUrl, model, timeout };
      if (apiKey) body.api_key = apiKey; // only send when a new key is entered
      const updated = await api.updateLlmConfig(body);
      setCfg(updated);
      setApiKey(""); // clear the field; never keep the secret in component state
      setMsg("Saved (runtime — not persisted; set .env for durability).");
    } catch (e) {
      setMsg(String((e as Error).message));
    } finally {
      setBusy("");
    }
  };

  const runTest = async () => {
    setBusy("test");
    setTest(null);
    try {
      setTest(await api.testLlm());
    } catch (e) {
      setMsg(String((e as Error).message));
    } finally {
      setBusy("");
      load();
    }
  };

  const stage = (ok: boolean | null, label: string) => (
    <Pill tone={ok === true ? "ok" : ok === false ? "crit" : "muted"} dot>
      {label}
    </Pill>
  );

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Panel
        title="AI Provider (centralized planner)"
        sub="Any OpenAI-compatible gateway — OpenRouter, a self-hosted OmniRoute, or another /v1 endpoint. The key is write-only and never returned by the backend."
        actions={cfg ? <Pill tone={cfg.config_valid ? "ok" : "warn"}>{cfg.config_valid ? "CONFIG VALID" : "INCOMPLETE"}</Pill> : undefined}
      >
        {!cfg ? (
          <Empty>Loading configuration…</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted">
              Provider
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="h-8 rounded border border-line bg-canvas px-2 text-sm text-ink outline-none focus:border-accent"
              >
                {cfg.supported_providers.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted">
              Base URL <span className="text-faint">(e.g. http://127.0.0.1:20128/v1 for OmniRoute — confirm the port)</span>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="empty = OpenRouter default"
                className="h-8 rounded border border-line bg-canvas px-2.5 text-sm text-ink outline-none placeholder:text-faint focus:border-accent"
              />
            </label>
            <div className="flex gap-3">
              <label className="flex flex-1 flex-col gap-1 text-xs text-muted">
                Model
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="empty = OPENROUTER_MODEL"
                  className="h-8 rounded border border-line bg-canvas px-2.5 text-sm text-ink outline-none placeholder:text-faint focus:border-accent"
                />
              </label>
              <label className="flex w-28 flex-col gap-1 text-xs text-muted">
                Timeout (s)
                <input
                  type="number"
                  min={5}
                  max={300}
                  value={timeout}
                  onChange={(e) => setTimeoutS(Number(e.target.value))}
                  className="h-8 rounded border border-line bg-canvas px-2.5 text-sm text-ink outline-none focus:border-accent"
                />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-xs text-muted">
              API key{" "}
              <span className="text-faint">
                {cfg.api_key_configured ? "— a key is configured (hidden). Enter a new one to replace it." : "— not configured."}
              </span>
              <input
                type="password"
                value={apiKey}
                autoComplete="new-password"
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={cfg.api_key_configured ? "•••••••• (leave blank to keep)" : "enter provider/gateway key"}
                className="h-8 rounded border border-line bg-canvas px-2.5 text-sm text-ink outline-none placeholder:text-faint focus:border-accent"
              />
            </label>
            <p className="text-2xs text-faint">
              Runtime changes are non-persistent (reset on backend restart). For durability set LLM_* / OPENROUTER_* in the
              backend <code className="font-mono">.env</code>. The key is held backend-side only — never stored in the browser.
            </p>
            <div className="flex items-center gap-2">
              <Button variant="primary" onClick={save} disabled={busy !== ""}>
                {busy === "save" ? "Saving…" : "Save configuration"}
              </Button>
              <Button variant="ghost" onClick={runTest} disabled={busy !== ""}>
                {busy === "test" ? "Testing…" : "Test connection"}
              </Button>
              {cfg.api_key_configured ? <Tag>key: configured</Tag> : <Pill tone="warn">key: not set</Pill>}
            </div>
            {msg && <p className="text-xs text-muted">{msg}</p>}
            {!cfg.config_valid && <p className="text-xs text-warn">{cfg.reason}</p>}
            {cfg.last_test && (
              <div className="flex flex-col gap-1 rounded border border-line bg-canvas px-3 py-2 text-2xs text-muted">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-faint">Last test:</span>
                  <Pill tone={cfg.last_test.inference_ok ? "ok" : "crit"} dot>
                    {cfg.last_test.inference_ok ? "inference ok" : "failed"}
                  </Pill>
                  <span>{cfg.last_test.at}</span>
                </div>
                <div>
                  <span className="text-faint">Last successful connection test: </span>
                  {cfg.last_test.last_success_at ?? "— none yet —"}
                </div>
                {cfg.last_test.last_error && (
                  <div className="text-crit">
                    <span className="text-faint">Last error: </span>
                    {cfg.last_test.last_error}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Panel>

      {test && (
        <Panel title="Connection test result" sub="A real harmless inference, not just an HTTP health check.">
          <div className="flex flex-col gap-3">
            <SectionLabel index="01" label="Staged status" />
            <div className="flex flex-wrap gap-2">
              {stage(test.config_valid, "config valid")}
              {stage(test.gateway_reachable, "gateway reachable")}
              {stage(test.auth_ok, "auth ok")}
              {stage(test.inference_ok, "inference ok")}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <Tag>provider: {test.provider}</Tag>
              {test.model && <Tag>model: {test.model}</Tag>}
              <Tag>timeout: {test.timeout}s</Tag>
            </div>
            <p className="text-xs text-muted">{test.reason}</p>
            {test.reply_excerpt && (
              <p className="rounded border border-ok/30 bg-ok/5 px-3 py-2 font-mono text-xs text-ink">
                {test.reply_excerpt}
              </p>
            )}
            {test.errors.length > 0 && (
              <ul className="list-disc pl-4 text-xs text-crit">
                {test.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}
