export type ProviderCategory = "text" | "image" | "video";
export type ModelMode = "manual" | "cc_switch";
export type MediaProviderId = "openai_image" | "openai_sora" | "compatible";

export interface MediaProviderPreset {
  id: MediaProviderId;
  category: "image" | "video";
  label: string;
  defaultModel: string;
  defaultName: string;
  requiresEndpoint: boolean;
}

export const MEDIA_PROVIDER_PRESETS: MediaProviderPreset[] = [
  {
    id: "openai_image",
    category: "image",
    label: "OpenAI 图片生成",
    defaultModel: "dall-e-3",
    defaultName: "OpenAI 图片",
    requiresEndpoint: false,
  },
  {
    id: "compatible",
    category: "image",
    label: "兼容图片接口（高级）",
    defaultModel: "gpt-image-2",
    defaultName: "兼容图片接口",
    requiresEndpoint: true,
  },
  {
    id: "openai_sora",
    category: "video",
    label: "OpenAI Sora 视频",
    defaultModel: "sora-2",
    defaultName: "OpenAI Sora 视频",
    requiresEndpoint: false,
  },
  {
    id: "compatible",
    category: "video",
    label: "兼容视频接口（高级）",
    defaultModel: "sora-2",
    defaultName: "兼容视频接口",
    requiresEndpoint: true,
  },
];

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

export interface MediaProviderConfig {
  id: string;
  category: "image" | "video";
  name: string;
  enabled: boolean;
  is_default: boolean;
  provider: MediaProviderId;
  api_key: string;
  api_url: string;
  model: string;
}

export type ProviderConfig = TextProviderConfig | MediaProviderConfig;

export interface ModelConfigCenter {
  text: TextProviderConfig[];
  image: MediaProviderConfig[];
  video: MediaProviderConfig[];
}

export interface ProviderTaskConfig {
  category: "image" | "video";
  provider: MediaProviderId;
  api_key: string;
  api_url: string;
  model: string;
}

export function mediaProviderPreset(
  category: "image" | "video",
  provider: MediaProviderId,
): MediaProviderPreset {
  const preset = MEDIA_PROVIDER_PRESETS.find(
    (item) => item.category === category && item.id === provider,
  );
  if (!preset) throw new Error(`不支持的${category}服务商：${provider}`);
  return preset;
}

export function mediaProviderOptions(category: "image" | "video"): Array<{ label: string; value: MediaProviderId }> {
  return MEDIA_PROVIDER_PRESETS
    .filter((item) => item.category === category)
    .map((item) => ({ label: item.label, value: item.id }));
}

const DEFAULT_CENTER: ModelConfigCenter = {
  text: [],
  image: [],
  video: [],
};

function newId(category: ProviderCategory): string {
  const suffix = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${category}-${suffix}`;
}

export function createProviderConfig(category: ProviderCategory): ProviderConfig {
  const id = newId(category);
  if (category === "text") {
    return {
      id,
      category,
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
  const provider: MediaProviderId = "compatible";
  const preset = mediaProviderPreset(category, provider);
  return {
    id,
    category,
    name: preset.defaultName,
    enabled: true,
    is_default: false,
    provider,
    api_key: "",
    api_url: "https://api.qlhazycoder.top/v1",
    model: preset.defaultModel,
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
  const config = createProviderConfig("text");
  if (config.category !== "text") return null;
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

function parseMediaConfig(value: unknown, category: "image" | "video"): MediaProviderConfig | null {
  if (!isRecord(value)) return null;
  const config = createProviderConfig(category) as MediaProviderConfig;
  const provider = value.provider === "openai_image" || value.provider === "openai_sora" || value.provider === "compatible"
    ? value.provider
    : "compatible";
  const safeProvider = category === "image" && provider === "openai_sora"
    ? "compatible"
    : category === "video" && provider === "openai_image"
      ? "compatible"
      : provider;
  const preset = mediaProviderPreset(category, safeProvider);
  return {
    ...config,
    category,
    id: text(value.id, config.id),
    name: text(value.name, config.name),
    enabled: bool(value.enabled, config.enabled),
    is_default: bool(value.is_default, config.is_default),
    provider: safeProvider,
    api_key: text(value.api_key, ""),
    api_url: text(value.api_url, ""),
    model: text(value.model, preset.defaultModel),
  };
}

export function loadModelConfigCenter(rawCenter: unknown, legacy: unknown): ModelConfigCenter {
  const center: ModelConfigCenter = {
    text: [],
    image: [],
    video: [],
  };
  if (isRecord(rawCenter)) {
    center.text = Array.isArray(rawCenter.text)
      ? rawCenter.text.map(parseTextConfig).filter((item): item is TextProviderConfig => item !== null)
      : [];
    center.image = Array.isArray(rawCenter.image)
      ? rawCenter.image.map((item) => parseMediaConfig(item, "image")).filter((item): item is MediaProviderConfig => item !== null)
      : [];
    center.video = Array.isArray(rawCenter.video)
      ? rawCenter.video.map((item) => parseMediaConfig(item, "video")).filter((item): item is MediaProviderConfig => item !== null)
      : [];
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

export function getActiveProvider(
  center: ModelConfigCenter,
  category: ProviderCategory,
): ProviderConfig | null {
  const candidates = center[category].filter((item) => item.enabled);
  return candidates.find((item) => item.is_default) || candidates[0] || null;
}

export function toTaskProviderConfig(config: MediaProviderConfig): ProviderTaskConfig {
  return {
    category: config.category,
    provider: config.provider,
    api_key: config.api_key,
    api_url: config.api_url,
    model: config.model,
  };
}

export function emptyModelConfigCenter(): ModelConfigCenter {
  return {
    text: [...DEFAULT_CENTER.text],
    image: [...DEFAULT_CENTER.image],
    video: [...DEFAULT_CENTER.video],
  };
}
