export type ProviderCategory = "text";
export type ModelMode = "manual" | "cc_switch";

export interface TextProviderConfig {
  id: string;
  category: "text";
  name: string;
  enabled: boolean;
  is_default: boolean;
  mode: ModelMode;
  api_key: string;
  base_url: string;
  model: string;
  reasoning_effort: string;
}

export type ProviderConfig = TextProviderConfig;

export interface ModelConfigCenter {
  text: TextProviderConfig[];
}

function newId(): string {
  const suffix = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `text-${suffix}`;
}

export function createProviderConfig(): TextProviderConfig {
  return {
    id: newId(),
    category: "text",
    name: "新的文本配置",
    enabled: true,
    is_default: false,
    mode: "manual",
    api_key: "",
    base_url: "https://api.qlhazycoder.top/v1",
    model: "gpt-5.4",
    reasoning_effort: "auto",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function parseTextConfig(value: unknown): TextProviderConfig | null {
  if (!isRecord(value)) return null;
  const config = createProviderConfig();
  return {
    ...config,
    id: text(value.id, config.id),
    name: text(value.name, config.name),
    enabled: bool(value.enabled, config.enabled),
    is_default: bool(value.is_default, config.is_default),
    mode: value.mode === "cc_switch" ? "cc_switch" : "manual",
    api_key: text(value.api_key, ""),
    base_url: text(value.base_url, config.base_url),
    model: text(value.model, config.model),
    reasoning_effort: text(value.reasoning_effort, config.reasoning_effort),
  };
}

export function loadModelConfigCenter(rawCenter: unknown, legacy: unknown): ModelConfigCenter {
  const center: ModelConfigCenter = { text: [] };
  if (isRecord(rawCenter) && Array.isArray(rawCenter.text)) {
    center.text = rawCenter.text
      .map(parseTextConfig)
      .filter((item): item is TextProviderConfig => item !== null);
  }
  if (center.text.length === 0 && isRecord(legacy)) {
    const migrated = parseTextConfig({
      ...legacy,
      id: "text-migrated",
      name: legacy.mode === "cc_switch" ? "CC-Switch 文本配置" : "手动文本配置",
      enabled: true,
      is_default: true,
      category: "text",
    });
    if (migrated) center.text.push(migrated);
  }
  return center;
}

export function getActiveProvider(center: ModelConfigCenter): TextProviderConfig | null {
  const candidates = center.text.filter((item) => item.enabled);
  return candidates.find((item) => item.is_default) || candidates[0] || null;
}

export function emptyModelConfigCenter(): ModelConfigCenter {
  return { text: [] };
}
