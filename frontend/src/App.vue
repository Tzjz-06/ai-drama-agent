<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  AddIcon,
  BrowseIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  CloseIcon,
  DeleteIcon,
  FileImportIcon,
  FilmIcon,
  LayersIcon,
  LockOnIcon,
  LogoutIcon,
  MoonIcon,
  MoveIcon,
  SettingIcon,
  SunnyIcon,
  TimeIcon,
  UserIcon,
  ViewListIcon,
  WalletIcon,
  EditIcon as WriteIcon,
} from "tdesign-icons-vue-next";
import { MessagePlugin } from "tdesign-vue-next";
import {
  createProviderConfig,
  getActiveProvider,
  loadModelConfigCenter,
  type ModelConfigCenter,
  type ModelMode,
  type ProviderConfig,
  type TextProviderConfig,
} from "./model-config";

type Route = "projects" | "script" | "assets" | "storyboard";
type AuthMode = "login" | "register";
type StudioTheme = "dark" | "light";

interface User {
  id: string;
  username: string;
  email: string;
}
interface CCSwitchRuntime {
  available: boolean;
  provider_id: string;
  provider_name: string;
  model: string;
  wire_api: string;
  provider_base_url: string;
  reasoning_effort: string;
  proxy_enabled: boolean;
  listen_address: string;
  listen_port: number;
  proxy_base_url: string;
  proxy_running: boolean;
  proxy_status: string;
  provider_healthy: boolean;
  provider_last_error: string;
  protocol_endpoint: string;
  db_path: string;
  error?: string;
}
interface ProjectSummary {
  id: string;
  title: string;
  description: string;
  style: string;
  genre: string;
  aspect_ratio: string;
  status: string;
  chapter_count: number;
  latest_chapter_title: string;
  character_count: number;
  scene_count: number;
  shot_count: number;
  updated_at: string;
}
interface Chapter {
  id: string;
  title: string;
  episode_no: number;
  outline: string;
  content: string;
  status: string;
  is_locked: boolean;
  production: Production | null;
}
interface Production {
  title: string;
  characters: Character[];
  scenes: Scene[];
  props: Prop[];
  shots: Shot[];
  continuity_issues: ContinuityIssue[];
  metadata?: Record<string, unknown>;
}
interface Character {
  id: string;
  name: string;
  role: string;
  appearance: string;
  costume: string;
  turnaround_prompt: string;
  status: string;
}
interface Scene {
  id: string;
  name: string;
  location: string;
  time: string;
  lighting: string;
  layout: string;
  environment_prompt: string;
  status: string;
}
interface Prop {
  id: string;
  name: string;
  description: string;
  owner: string;
}
type Asset = Character | Scene | Prop;
interface AssetDraft {
  [key: string]: string;
  id: string;
  name: string;
}
interface ContinuityIssue {
  severity: string;
  scope: string;
  message: string;
  suggested_action: string;
}
interface Shot {
  id: string;
  scene_id: string;
  character_ids: string[];
  prop_ids: string[];
  start_second: number;
  duration_seconds: number;
  shot_size: string;
  camera_position: string;
  lens: string;
  camera_motion: string;
  visual_action: string;
  dialogue: string;
  sound_design: string;
  first_frame_prompt: string;
  video_prompt: string;
  last_frame_prompt: string;
  negative_prompt: string;
  confidence: string;
  status: string;
}
interface QuickProgress {
  status: "idle" | "running" | "completed" | "failed";
  percent: number;
  stage: string;
  message: string;
  error: string;
}

const tokenKey = "jiaozi-auth-token";
const modelConfigKey = "jiaozi-model-config";
const modelConfigCenterKey = "jiaozi-model-config-center";
const themeKey = "jiaozi-studio-theme";
function readPersistentValue(key: string): string | null {
  return localStorage.getItem(key) || sessionStorage.getItem(key);
}
const theme = ref<StudioTheme>(
  localStorage.getItem(themeKey) === "light" ? "light" : "dark",
);
const token = ref(readPersistentValue(tokenKey) || "");
const user = ref<User | null>(null);
const authMode = ref<AuthMode>("login");
const authBusy = ref(false);
const authForm = ref({ identity: "", username: "", email: "", password: "" });
const authError = ref("");

const route = ref<Route>("projects");
const projects = ref<ProjectSummary[]>([]);
const currentProject = ref<ProjectSummary | null>(null);
const currentProjectDetail = ref<{ chapters: Chapter[] } | null>(null);
const currentChapter = ref<Chapter | null>(null);
const activeShot = ref<Shot | null>(null);
const assetTab = ref<"characters" | "scenes" | "props">("characters");
const showAssetEditor = ref(false);
const editingAsset = ref<AssetDraft | null>(null);
const editingAssetType = ref<"characters" | "scenes" | "props">("characters");
const assetSaving = ref(false);
const showShotPromptEditor = ref(false);
const editingShotPrompts = ref<Pick<Shot, "id" | "first_frame_prompt" | "video_prompt" | "last_frame_prompt" | "negative_prompt"> | null>(null);
const shotPromptSaving = ref(false);
const search = ref("");
const loading = ref(false);
const generating = ref(false);
const chapterSaving = ref(false);
const showCreateProject = ref(false);
const showQuickCreate = ref(false);
const showCreateChapter = ref(false);
const projectCreating = ref(false);
const quickCreating = ref(false);
const quickProgress = ref<QuickProgress>({
  status: "idle",
  percent: 0,
  stage: "等待开始",
  message: "提交后将显示真实生成阶段",
  error: "",
});
const quickProgressTarget = ref(0);
let quickProgressTimer: ReturnType<typeof setInterval> | null = null;
let quickProgressAnimation: ReturnType<typeof setInterval> | null = null;
const deletingProject = ref(false);
const projectPendingDeletion = ref<ProjectSummary | null>(null);
const showDeleteProject = ref(false);
const importingScript = ref(false);
const scriptFileInput = ref<HTMLInputElement | null>(null);
const showSettings = ref(false);
const exportingPackage = ref(false);
const projectDraft = ref({
  title: "",
  genre: "都市情感",
  style: "电影感二维国漫",
  aspect_ratio: "9:16",
  description: "",
});
const genreOptions = ref([
  "都市情感",
  "悬疑推理",
  "古装权谋",
  "仙侠玄幻",
  "科幻未来",
  "轻喜剧",
  "家庭伦理",
  "青春校园",
  "逆袭爽剧",
].map((value) => ({ label: value, value })));
const visualStyleOptions = ref([
  "电影感二维国漫",
  "写实电影感",
  "电影级三渲二",
  "新中式水墨",
  "日系动画",
  "复古港风",
  "赛博朋克",
  "黑白漫画",
].map((value) => ({ label: value, value })));
const quickIdea = ref({ title: "", brief: "" });
const chapterDraft = ref({ title: "", outline: "", content: "" });
const savedModelConfigCenter = readPersistentValue(modelConfigCenterKey);
const savedModelConfig = readPersistentValue(modelConfigKey);
function readSessionJson(value: string | null): unknown {
  if (!value) return null;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}
const modelConfigCenter = ref<ModelConfigCenter>(
  loadModelConfigCenter(
    readSessionJson(savedModelConfigCenter),
    readSessionJson(savedModelConfig),
  ),
);
if (savedModelConfigCenter && !localStorage.getItem(modelConfigCenterKey)) {
  localStorage.setItem(modelConfigCenterKey, savedModelConfigCenter);
}
if (savedModelConfig && !localStorage.getItem(modelConfigKey)) {
  localStorage.setItem(modelConfigKey, savedModelConfig);
}
document.documentElement.dataset.studioTheme = theme.value;
const editingConfigId = ref<string | null>(null);
const editingConfig = ref<ProviderConfig | null>(null);
const offlineDemo = ref(false);
const environmentModelConfigured = ref(false);
const environmentModel = ref("gpt-5.4");
const ccSwitchRuntime = ref<CCSwitchRuntime>(emptyCcSwitchRuntime());
const modelTestBusy = ref(false);
const modelStatus = ref<{
  state: "idle" | "testing" | "success" | "error";
  message: string;
}>({ state: "idle", message: "尚未测试当前配置" });
const activeTextConfig = computed(
  () => getActiveProvider(modelConfigCenter.value) as TextProviderConfig | null,
);
const isCcSwitchMode = computed(
  () => activeTextConfig.value?.mode === "cc_switch",
);
const ccSwitchReady = computed(
  () =>
    ccSwitchRuntime.value.available &&
    ccSwitchRuntime.value.proxy_enabled &&
    ccSwitchRuntime.value.proxy_running &&
    ["responses", "chat_completions", "chat-completions"].includes(
      ccSwitchRuntime.value.wire_api,
    ),
);
const ccSwitchStatusMessage = computed(() => {
  const runtime = ccSwitchRuntime.value;
  if (!runtime.available) return runtime.error || "未检测到 CC-Switch 运行态。";
  if (!runtime.proxy_enabled) return "CC-Switch Codex 代理未启用。";
  if (!runtime.proxy_running)
    return `CC-Switch 本地代理不可用（${runtime.proxy_status || "unavailable"}）。`;
  if (
    !["responses", "chat_completions", "chat-completions"].includes(
      runtime.wire_api,
    )
  ) {
    return `当前协议是 ${runtime.wire_api}，饺子短剧暂时不支持该协议。`;
  }
  return `CC-Switch 代理正常 · ${runtime.provider_name || "当前供应商"} · ${runtime.model || "未配置模型"} · ${runtime.wire_api}`;
});

const production = computed(() => currentChapter.value?.production || null);
const shots = computed(() => production.value?.shots || []);
const filteredProjects = computed(() =>
  projects.value.filter((item) =>
    item.title.toLowerCase().includes(search.value.toLowerCase()),
  ),
);
const assets = computed(() => production.value?.[assetTab.value] || []);
const progress = computed(() => {
  if (!production.value || shots.value.length === 0) return 0;
  const ready = shots.value.filter(
    (shot) => shot.status === "confirmed",
  ).length;
  return Math.round((ready / shots.value.length) * 100);
});

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token.value) headers.set("Authorization", `Bearer ${token.value}`);
  const response = await fetch(path, { ...init, headers });
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok)
    throw new Error(payload.error || `请求失败：HTTP ${response.status}`);
  return payload;
}

async function submitAuth(): Promise<void> {
  authBusy.value = true;
  authError.value = "";
  try {
    if (authMode.value === "login") {
      const result = await request<{ token: string; user: User }>(
        "/api/auth/login",
        {
          method: "POST",
          body: JSON.stringify({
            identity: authForm.value.identity,
            password: authForm.value.password,
          }),
        },
      );
      token.value = result.token;
      user.value = result.user;
      localStorage.setItem(tokenKey, result.token);
      sessionStorage.removeItem(tokenKey);
      await loadProjects();
    } else {
      await request("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: authForm.value.username,
          email: authForm.value.email,
          password: authForm.value.password,
        }),
      });
      authMode.value = "login";
      authForm.value.identity = authForm.value.username;
      await submitAuth();
    }
  } catch (error) {
    authError.value =
      error instanceof Error ? error.message : "操作失败，请稍后重试。";
  } finally {
    authBusy.value = false;
  }
}

async function loadProjects(): Promise<void> {
  const result = await request<{ projects: ProjectSummary[] }>("/api/projects");
  projects.value = result.projects;
  if (currentProject.value) {
    const refreshed = projects.value.find(
      (item) => item.id === currentProject.value?.id,
    );
    if (refreshed) currentProject.value = refreshed;
  }
}

async function openProject(project: ProjectSummary): Promise<void> {
  loading.value = true;
  try {
    const result = await request<{
      project: ProjectSummary & { chapters: Chapter[] };
    }>(`/api/projects/${project.id}`);
    currentProject.value = result.project;
    currentProjectDetail.value = result.project;
    currentChapter.value = result.project.chapters[0] || null;
    if (currentChapter.value) setChapterDraft(currentChapter.value);
    route.value = "script";
  } catch (error) {
    await showError(error);
  } finally {
    loading.value = false;
  }
}

function setChapterDraft(chapter: Chapter): void {
  chapterDraft.value = {
    title: chapter.title,
    outline: chapter.outline,
    content: chapter.content,
  };
}
function selectChapter(chapter: Chapter): void {
  currentChapter.value = chapter;
  setChapterDraft(chapter);
  route.value = "script";
}

async function createProject(): Promise<void> {
  if (projectCreating.value) return;
  projectCreating.value = true;
  try {
    const result = await request<{ project: ProjectSummary }>("/api/projects", {
      method: "POST",
      body: JSON.stringify(projectDraft.value),
    });
    projects.value.unshift(result.project);
    closeCreateProject();
    await openProject(result.project);
    projectDraft.value = {
      title: "",
      genre: "都市情感",
      style: "电影感二维国漫",
      aspect_ratio: "9:16",
      description: "",
    };
    await MessagePlugin.success("项目已建立");
  } catch (error) {
    await showError(error);
  } finally {
    projectCreating.value = false;
  }
}

async function ensureTextModelReady(): Promise<boolean> {
  if (offlineDemo.value) return true;
  const textConfig = activeTextConfig.value;
  if (textConfig?.mode === "cc_switch") {
    await refreshRuntimeStatus();
    if (!ccSwitchReady.value) {
      showSettings.value = true;
      modelStatus.value = {
        state: "error",
        message: ccSwitchStatusMessage.value,
      };
      await MessagePlugin.warning(ccSwitchStatusMessage.value);
      return false;
    }
  } else if (!textConfig && !environmentModelConfigured.value) {
    showSettings.value = true;
    await MessagePlugin.warning("请先添加并启用一个文本模型配置");
    return false;
  } else if (
    textConfig &&
    !textConfig.api_key &&
    !environmentModelConfigured.value
  ) {
    showSettings.value = true;
    await MessagePlugin.warning("请先配置并测试模型 API");
    return false;
  }
  return true;
}

async function createFromOneSentence(): Promise<void> {
  const brief = quickIdea.value.brief.trim();
  if (!brief) {
    await MessagePlugin.warning("请先写下一句话梗概或故事想法");
    return;
  }
  if (quickCreating.value || !(await ensureTextModelReady())) return;
  quickCreating.value = true;
  const progressId = crypto.randomUUID();
  quickProgressTarget.value = 0;
  quickProgress.value = {
    status: "running",
    percent: 0,
    stage: "准备创作",
    message: "正在提交创作任务",
    error: "",
  };
  const pollProgress = async (): Promise<void> => {
    try {
      const result = await request<{ progress: QuickProgress }>(
        `/api/progress/${progressId}`,
      );
      quickProgressTarget.value = Math.max(
        0,
        Math.min(100, result.progress.percent ?? 0),
      );
      quickProgress.value = {
        ...result.progress,
        percent: quickProgress.value.percent,
      };
    } catch {
      // The progress entry may not exist during the first request round trip.
    }
  };
  quickProgressAnimation = setInterval(() => {
    const current = quickProgress.value.percent;
    if (quickProgress.value.status === "completed" && current < 100) {
      quickProgress.value = {
        ...quickProgress.value,
        percent: Math.min(100, current + 0.75),
      };
      return;
    }
    if (quickProgress.value.status !== "running" || current >= 99) return;
    const increment = current < 60 ? 0.12 : current < 85 ? 0.05 : 0.01;
    quickProgress.value = {
      ...quickProgress.value,
      percent: Math.min(99, current + increment),
    };
  }, 80);
  quickProgressTimer = setInterval(() => void pollProgress(), 700);
  try {
    const textConfig = activeTextConfig.value;
    const result = await request<{
      project: ProjectSummary & { chapters: Chapter[] };
      chapter: Chapter;
      production: Production;
    }>("/api/projects/quick-create", {
      method: "POST",
      body: JSON.stringify({
        title: quickIdea.value.title.trim() || "一句话短剧",
        brief,
        genre: "短剧",
        style: "电影感二维国漫",
        aspect_ratio: "9:16",
        progress_id: progressId,
        model_config: textConfig || undefined,
      }),
    });
    result.chapter.production = result.production;
    currentProject.value = result.project;
    currentProjectDetail.value = result.project;
    currentChapter.value = result.chapter;
    setChapterDraft(result.chapter);
    activeShot.value = shots.value[0] || null;
    route.value = "storyboard";
    quickProgressTarget.value = 100;
    quickProgress.value = {
      status: "completed",
      percent: quickProgress.value.percent,
      stage: "资产与分镜已完成",
      message: "剧本、资产和分镜提示词已生成并保存",
      error: "",
    };
    await new Promise<void>((resolve) => {
      const waitForProgress = window.setInterval(() => {
        if (quickProgress.value.percent >= 100) {
          window.clearInterval(waitForProgress);
          resolve();
        }
      }, 40);
    });
    await new Promise((resolve) => setTimeout(resolve, 450));
    showQuickCreate.value = false;
    quickIdea.value = { title: "", brief: "" };
    await loadProjects();
    await MessagePlugin.success("剧本和分镜提示词已生成");
  } catch (error) {
    await pollProgress();
    if (quickProgress.value.status !== "failed") {
      quickProgress.value = {
        ...quickProgress.value,
        status: "failed",
        error: error instanceof Error ? error.message : "生成失败",
      };
    }
    await showError(error);
  } finally {
    if (quickProgressTimer) clearInterval(quickProgressTimer);
    if (quickProgressAnimation) clearInterval(quickProgressAnimation);
    quickProgressTimer = null;
    quickProgressAnimation = null;
    quickCreating.value = false;
    if (!showQuickCreate.value) {
      quickProgress.value = {
        status: "idle",
        percent: 0,
        stage: "等待开始",
        message: "提交后将显示真实生成阶段",
        error: "",
      };
    }
  }
}

watch(showQuickCreate, (visible) => {
  if (!visible && !quickCreating.value) {
    quickProgress.value = {
      status: "idle",
      percent: 0,
      stage: "等待开始",
      message: "提交后将显示真实生成阶段",
      error: "",
    };
  }
});

function requestProjectDeletion(project: ProjectSummary): void {
  projectPendingDeletion.value = project;
  showDeleteProject.value = true;
}

async function deleteProject(): Promise<void> {
  const project = projectPendingDeletion.value;
  if (!project || deletingProject.value) return;
  deletingProject.value = true;
  try {
    await request(`/api/projects/${project.id}`, { method: "DELETE" });
    projects.value = projects.value.filter((item) => item.id !== project.id);
    if (currentProject.value?.id === project.id) {
      currentProject.value = null;
      currentProjectDetail.value = null;
      currentChapter.value = null;
      activeShot.value = null;
    }
    projectPendingDeletion.value = null;
    showDeleteProject.value = false;
    route.value = "projects";
    await MessagePlugin.success("项目及其本地任务已删除");
  } catch (error) {
    await showError(error);
  } finally {
    deletingProject.value = false;
  }
}

async function createChapter(): Promise<void> {
  if (!currentProject.value) return;
  try {
    const result = await request<{ chapter: Chapter }>(
      `/api/projects/${currentProject.value.id}/chapters`,
      {
        method: "POST",
        body: JSON.stringify({ title: chapterDraft.value.title || "新章节" }),
      },
    );
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters.push(result.chapter);
    selectChapter(result.chapter);
    showCreateChapter.value = false;
    await MessagePlugin.success("章节已创建");
  } catch (error) {
    await showError(error);
  }
}

async function saveChapter(successMessage = "章节已保存"): Promise<boolean> {
  if (!currentProject.value || !currentChapter.value) return false;
  chapterSaving.value = true;
  try {
    const result = await request<{ chapter: Chapter }>(
      `/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}`,
      { method: "PATCH", body: JSON.stringify(chapterDraft.value) },
    );
    currentChapter.value = result.chapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((item) =>
          item.id === result.chapter.id ? result.chapter : item,
        );
    await MessagePlugin.success(successMessage);
    return true;
  } catch (error) {
    await showError(error);
    return false;
  } finally {
    chapterSaving.value = false;
  }
}

function openAssetEditor(item: Asset): void {
  editingAssetType.value = assetTab.value;
  editingAsset.value = { ...item };
  showAssetEditor.value = true;
}

function closeAssetEditor(): void {
  if (assetSaving.value) return;
  showAssetEditor.value = false;
  editingAsset.value = null;
}

function setCustomProjectOption(
  field: "genre" | "style",
  value: string | number | boolean | bigint,
): void {
  const customValue = String(value).trim();
  if (!customValue) return;
  const options = field === "genre" ? genreOptions.value : visualStyleOptions.value;
  if (!options.some((option) => option.value === customValue)) {
    options.push({ label: customValue, value: customValue });
  }
  projectDraft.value[field] = customValue;
}

async function saveAsset(): Promise<void> {
  if (
    assetSaving.value ||
    !currentProject.value ||
    !currentChapter.value ||
    !editingAsset.value
  )
    return;
  if (!editingAsset.value.name.trim()) {
    await MessagePlugin.warning("资产名称不能为空");
    return;
  }
  assetSaving.value = true;
  try {
    const result = await request<{ chapter: Chapter }>(
      `/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/assets/${editingAssetType.value}/${encodeURIComponent(editingAsset.value.id)}`,
      { method: "PATCH", body: JSON.stringify(editingAsset.value) },
    );
    currentChapter.value = result.chapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((item) =>
          item.id === result.chapter.id ? result.chapter : item,
        );
    showAssetEditor.value = false;
    editingAsset.value = null;
    await MessagePlugin.success("资产已保存");
  } catch (error) {
    await showError(error);
  } finally {
    assetSaving.value = false;
  }
}

function openShotPromptEditor(): void {
  if (!activeShot.value) return;
  editingShotPrompts.value = {
    id: activeShot.value.id,
    first_frame_prompt: activeShot.value.first_frame_prompt || "",
    video_prompt: activeShot.value.video_prompt || "",
    last_frame_prompt: activeShot.value.last_frame_prompt || "",
    negative_prompt: activeShot.value.negative_prompt || "",
  };
  showShotPromptEditor.value = true;
}

function closeShotPromptEditor(): void {
  if (shotPromptSaving.value) return;
  showShotPromptEditor.value = false;
  editingShotPrompts.value = null;
}

async function saveShotPrompts(): Promise<void> {
  if (
    shotPromptSaving.value ||
    !currentProject.value ||
    !currentChapter.value ||
    !editingShotPrompts.value
  )
    return;
  shotPromptSaving.value = true;
  try {
    const shotId = editingShotPrompts.value.id;
    const result = await request<{ chapter: Chapter }>(
      `/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/shots/${encodeURIComponent(shotId)}`,
      { method: "PATCH", body: JSON.stringify(editingShotPrompts.value) },
    );
    currentChapter.value = result.chapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((item) =>
          item.id === result.chapter.id ? result.chapter : item,
        );
    activeShot.value = result.chapter.production?.shots.find(
      (shot) => shot.id === shotId,
    ) || null;
    showShotPromptEditor.value = false;
    editingShotPrompts.value = null;
    await MessagePlugin.success("分镜提示词已保存");
  } catch (error) {
    await showError(error);
  } finally {
    shotPromptSaving.value = false;
  }
}

function chooseScriptFile(): void {
  scriptFileInput.value?.click();
}

function handleImportButtonClick(event: Event): void {
  const target = event.target;
  if (target instanceof Element && target.closest(".import-button")) {
    event.preventDefault();
    chooseScriptFile();
  }
}

async function encodeFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("无法读取所选文件"));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("无法读取所选文件"));
        return;
      }
      const separator = reader.result.indexOf(",");
      resolve(
        separator >= 0 ? reader.result.slice(separator + 1) : reader.result,
      );
    };
    reader.readAsDataURL(file);
  });
}

async function importScriptFromFile(event: Event): Promise<void> {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !currentProject.value || !currentChapter.value) return;
  if (file.size > 12 * 1024 * 1024) {
    await MessagePlugin.warning("剧本文档不能超过 12MB");
    return;
  }

  importingScript.value = true;
  try {
    const result = await request<{
      script: string;
      filename: string;
      source_label: string;
    }>("/api/import-script", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_base64: await encodeFileAsBase64(file),
        ocr_mode: "auto",
      }),
    });
    chapterDraft.value.content = result.script;
    await saveChapter(`已导入并保存 ${result.source_label}`);
  } catch (error) {
    await showError(error);
  } finally {
    importingScript.value = false;
  }
}

async function generateProduction(): Promise<void> {
  if (
    !currentProject.value ||
    !currentChapter.value ||
    !chapterDraft.value.content.trim()
  ) {
    await MessagePlugin.warning("请先选择章节并录入剧本正文");
    return;
  }
  const textConfig = activeTextConfig.value;
  if (textConfig?.mode === "cc_switch") {
    await refreshRuntimeStatus();
    if (!ccSwitchReady.value) {
      showSettings.value = true;
      modelStatus.value = {
        state: "error",
        message: ccSwitchStatusMessage.value,
      };
      await MessagePlugin.warning(ccSwitchStatusMessage.value);
      return;
    }
  } else if (!textConfig && !environmentModelConfigured.value) {
    showSettings.value = true;
    await MessagePlugin.warning("请先添加并启用一个文本模型配置");
    return;
  } else if (
    textConfig &&
    !textConfig.api_key &&
    !environmentModelConfigured.value
  ) {
    showSettings.value = true;
    await MessagePlugin.warning("请先配置并测试模型 API");
    return;
  }
  generating.value = true;
  try {
    await saveChapter();
    const result = await request<{ project: Production; chapter: Chapter }>(
      `/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/generate`,
      {
        method: "POST",
        body: JSON.stringify({
          script: chapterDraft.value.content,
          style: currentProject.value.style,
          aspect_ratio: currentProject.value.aspect_ratio,
          fps: 24,
          target_model: "model-agnostic",
          model_config: textConfig || undefined,
        }),
      },
    );
    currentChapter.value = result.chapter;
    currentChapter.value.production = result.project;
    route.value = "storyboard";
    activeShot.value = shots.value[0] || null;
    await loadProjects();
    await MessagePlugin.success("实体与分镜已生成");
  } catch (error) {
    await showError(error);
  } finally {
    generating.value = false;
  }
}

async function showError(error: unknown): Promise<void> {
  await MessagePlugin.error(
    error instanceof Error ? error.message : "操作失败",
  );
}
function closeCreateProject(): void {
  showCreateProject.value = false;
}
function persistModelConfigCenter(): void {
  localStorage.setItem(
    modelConfigCenterKey,
    JSON.stringify(modelConfigCenter.value),
  );
  sessionStorage.removeItem(modelConfigCenterKey);
  sessionStorage.removeItem(modelConfigKey);
}

function openConfigEditor(config: ProviderConfig): void {
  editingConfigId.value = config.id;
  editingConfig.value = { ...config };
}

function createConfig(): void {
  const config = createProviderConfig();
  const list = modelConfigCenter.value.text;
  if (list.length === 0) config.is_default = true;
  list.push(config);
  persistModelConfigCenter();
  openConfigEditor(config);
}

function deleteConfig(config: ProviderConfig): void {
  const list = modelConfigCenter.value[config.category];
  const index = list.findIndex((item) => item.id === config.id);
  if (index < 0) return;
  list.splice(index, 1);
  if (config.is_default && list[0]) list[0].is_default = true;
  if (editingConfigId.value === config.id) {
    editingConfigId.value = null;
    editingConfig.value = null;
  }
  persistModelConfigCenter();
}

function setDefaultConfig(config: ProviderConfig): void {
  const list = modelConfigCenter.value[config.category];
  for (const item of list) item.is_default = item.id === config.id;
  persistModelConfigCenter();
}

function saveConfigEditor(): void {
  const config = editingConfig.value;
  if (!config || !config.name.trim()) return;
  const list = modelConfigCenter.value[config.category];
  const index = list.findIndex((item) => item.id === config.id);
  if (index >= 0) list[index] = { ...config } as never;
  persistModelConfigCenter();
  MessagePlugin.success("配置已保存，仅保存在当前浏览器会话");
}

async function testProviderConnection(config: ProviderConfig): Promise<void> {
  modelTestBusy.value = true;
  modelStatus.value = {
    state: "testing",
    message: `正在测试 ${config.name}...`,
  };
  try {
    const result = await request<{
      mode: ModelMode;
      model: string;
      provider: string;
      wire_api: string;
      elapsed_ms: number;
    }>("/api/model/test", {
      method: "POST",
      body: JSON.stringify({ model_config: config }),
    });
    modelStatus.value = {
      state: "success",
      message:
        result.mode === "cc_switch"
          ? `连接成功 · ${result.provider || "CC-Switch"} · ${result.model} · ${result.wire_api} · ${result.elapsed_ms} ms`
          : `连接成功 · ${result.model} · ${result.elapsed_ms} ms`,
    };
    persistModelConfigCenter();
  } catch (error) {
    modelStatus.value = {
      state: "error",
      message: error instanceof Error ? error.message : "连接测试失败",
    };
  } finally {
    modelTestBusy.value = false;
  }
}

function saveModelSettings(): void {
  persistModelConfigCenter();
  showSettings.value = false;
  resetModelStatus();
  MessagePlugin.success("模型来源已保存");
}
async function testModelConnection(): Promise<void> {
  modelTestBusy.value = true;
  if (isCcSwitchMode.value) await refreshRuntimeStatus();
  modelStatus.value = {
    state: "testing",
    message: isCcSwitchMode.value
      ? "正在验证 CC-Switch 当前供应商与本地代理..."
      : "正在验证 API Key、Base URL 和模型...",
  };
  try {
    const result = await request<{
      mode: ModelMode;
      model: string;
      base_url: string;
      provider: string;
      wire_api: string;
      elapsed_ms: number;
    }>("/api/model/test", {
      method: "POST",
      body: JSON.stringify({
        model_config: activeTextConfig.value || undefined,
      }),
    });
    persistModelConfigCenter();
    modelStatus.value = {
      state: "success",
      message:
        result.mode === "cc_switch"
          ? `连接成功 · ${result.provider || "CC-Switch"} · ${result.model} · ${result.wire_api} · ${result.elapsed_ms} ms`
          : `连接成功 · ${result.model} · ${result.elapsed_ms} ms`,
    };
  } catch (error) {
    modelStatus.value = {
      state: "error",
      message: error instanceof Error ? error.message : "连接测试失败",
    };
  } finally {
    modelTestBusy.value = false;
  }
}
function toggleTheme(): void {
  theme.value = theme.value === "dark" ? "light" : "dark";
  localStorage.setItem(themeKey, theme.value);
  document.documentElement.dataset.studioTheme = theme.value;
}
function logout(): void {
  token.value = "";
  user.value = null;
  localStorage.removeItem(tokenKey);
  sessionStorage.removeItem(tokenKey);
  currentProject.value = null;
}
function exitProject(): void {
  currentProject.value = null;
  currentProjectDetail.value = null;
  currentChapter.value = null;
  activeShot.value = null;
  route.value = "projects";
}
function setRoute(next: Route): void {
  route.value = next;
  if (next === "storyboard") activeShot.value = shots.value[0] || null;
}
async function copyPrompt(text: string): Promise<void> {
  if (!text.trim()) {
    await MessagePlugin.warning("当前没有可复制的提示词");
    return;
  }
  try {
    if (navigator.clipboard?.writeText)
      await navigator.clipboard.writeText(text);
    else copyPromptWithFallback(text);
    await MessagePlugin.success("提示词已复制");
  } catch {
    try {
      copyPromptWithFallback(text);
      await MessagePlugin.success("提示词已复制");
    } catch (error) {
      await showError(error);
    }
  }
}

function copyPromptWithFallback(text: string): void {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("浏览器阻止了复制，请检查剪贴板权限。");
}

async function exportProductionPackage(): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId || !production.value || exportingPackage.value)
    return;
  exportingPackage.value = true;
  try {
    const response = await fetch(
      `/api/projects/${projectId}/chapters/${chapterId}/production.zip`,
      {
        headers: { Authorization: `Bearer ${token.value}` },
      },
    );
    if (!response.ok) {
      const payload = (await response.json()) as { error?: string };
      throw new Error(payload.error || `导出失败：HTTP ${response.status}`);
    }
    const content = await response.blob();
    const url = URL.createObjectURL(content);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${currentProject.value?.title || "项目"}-${currentChapter.value?.title || "章节"}-剧本和分镜.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    await MessagePlugin.success("剧本和分镜已一键导出");
  } catch (error) {
    await showError(error);
  } finally {
    exportingPackage.value = false;
  }
}
function statusLabel(value: string): string {
  return (
    {
      draft: "草稿",
      completed: "已完成",
      confirmed: "已锁定",
      待确认: "待确认",
    }[value] || value
  );
}

async function refreshRuntimeStatus(): Promise<void> {
  try {
    const runtime = await request<{
      offline_demo: boolean;
      environment_model_configured: boolean;
      environment_model: string;
      cc_switch: CCSwitchRuntime;
    }>("/api/runtime");
    offlineDemo.value = runtime.offline_demo;
    environmentModelConfigured.value = runtime.environment_model_configured;
    environmentModel.value = runtime.environment_model;
    ccSwitchRuntime.value = runtime.cc_switch;
  } catch (error) {
    offlineDemo.value = false;
    environmentModelConfigured.value = false;
    ccSwitchRuntime.value = {
      ...emptyCcSwitchRuntime(),
      error: error instanceof Error ? error.message : "运行态读取失败",
    };
  }
}

function resetModelStatus(): void {
  modelStatus.value = {
    state: "idle",
    message: isCcSwitchMode.value
      ? ccSwitchStatusMessage.value
      : "尚未测试当前配置",
  };
}

function emptyCcSwitchRuntime(): CCSwitchRuntime {
  return {
    available: false,
    provider_id: "",
    provider_name: "",
    model: "",
    wire_api: "",
    provider_base_url: "",
    reasoning_effort: "",
    proxy_enabled: false,
    listen_address: "",
    listen_port: 0,
    proxy_base_url: "",
    proxy_running: false,
    proxy_status: "unavailable",
    provider_healthy: false,
    provider_last_error: "",
    protocol_endpoint: "",
    db_path: "",
    error: "",
  };
}

watch(
  () => activeTextConfig.value?.mode,
  () => {
    if (isCcSwitchMode.value) void refreshRuntimeStatus();
    resetModelStatus();
  },
);

watch(showSettings, (visible) => {
  if (!visible) return;
  void refreshRuntimeStatus().then(() => {
    if (isCcSwitchMode.value) resetModelStatus();
  });
});

onMounted(async () => {
  document.addEventListener("click", handleImportButtonClick);
  const picker = document.createElement("input");
  picker.type = "file";
  picker.accept = ".txt,.docx,.pdf,.png,.jpg,.jpeg";
  picker.style.display = "none";
  picker.addEventListener("change", importScriptFromFile);
  document.body.appendChild(picker);
  scriptFileInput.value = picker;
  await refreshRuntimeStatus();
  resetModelStatus();
  if (!token.value) return;
  try {
    const me = await request<{ user: User }>("/api/auth/me");
    user.value = me.user;
    localStorage.setItem(tokenKey, token.value);
    sessionStorage.removeItem(tokenKey);
    await loadProjects();
  } catch {
    logout();
  }
});

onBeforeUnmount(() => {
  if (quickProgressTimer) clearInterval(quickProgressTimer);
  if (quickProgressAnimation) clearInterval(quickProgressAnimation);
  document.removeEventListener("click", handleImportButtonClick);
  scriptFileInput.value?.remove();
  scriptFileInput.value = null;
});
</script>

<template>
  <div
    v-if="!user"
    class="auth-shell"
    :class="{ 'theme-light': theme === 'light' }"
  >
    <section class="auth-art">
      <div class="brand-lockup">
        <span class="logo-dumpling" aria-hidden="true"></span
        ><span
          ><strong>饺子短剧</strong><small>JIAOZI DRAMA STUDIO</small></span
        >
      </div>
      <p class="eyebrow">AI STORY PRODUCTION</p>
      <h1>把一个故事，<br /><em>做成一部短剧。</em></h1>
      <p class="auth-lede">
        剧本、角色、场景、道具与逐镜提示词，在同一个创作流程里完成。
      </p>
      <div class="auth-stamp"><span>导演创作台</span><span>01 / 04</span></div>
    </section>
    <section class="auth-panel">
      <div class="auth-panel-top">
        <span class="mini-brand">饺子短剧</span><span>本地创作空间</span>
      </div>
      <div class="auth-form">
        <div class="auth-mode-tabs">
          <button
            :class="{ active: authMode === 'login' }"
            type="button"
            @click="authMode = 'login'"
          >
            登录</button
          ><button
            :class="{ active: authMode === 'register' }"
            type="button"
            @click="authMode = 'register'"
          >
            注册
          </button>
        </div>
        <span class="eyebrow">CREATOR ACCESS</span>
        <h2>{{ authMode === "login" ? "继续你的创作" : "创建创作者账户" }}</h2>
        <p>
          {{
            authMode === "login"
              ? "登录后进入项目管理台。"
              : "账户用于隔离这台设备上的项目数据。"
          }}
        </p>
        <t-form @submit="submitAuth"
          ><t-form-item v-if="authMode === 'register'" label="用户名"
            ><t-input
              v-model="authForm.username"
              placeholder="你的创作者名称" /></t-form-item
          ><t-form-item v-if="authMode === 'register'" label="邮箱"
            ><t-input
              v-model="authForm.email"
              placeholder="可选" /></t-form-item
          ><t-form-item v-else label="账号"
            ><t-input
              v-model="authForm.identity"
              placeholder="用户名或邮箱" /></t-form-item
          ><t-form-item label="密码"
            ><t-input
              v-model="authForm.password"
              type="password"
              placeholder="至少 6 位字符"
          /></t-form-item>
          <p v-if="authError" class="form-error">{{ authError }}</p>
          <t-button theme="primary" block type="submit" :loading="authBusy"
            >{{ authMode === "login" ? "进入创作台" : "创建并进入" }}
            <ChevronDownIcon /></t-button
        ></t-form>
      </div>
      <div class="auth-panel-foot">
        <span>你的内容只属于你的创作空间</span><LockOnIcon />
      </div>
    </section>
  </div>
  <div
    v-else
    class="studio-shell"
    :class="{ 'theme-light': theme === 'light' }"
  >
    <button
      v-if="route === 'projects' && currentProject"
      class="project-delete-launcher"
      type="button"
      title="删除当前项目"
      @click="requestProjectDeletion(currentProject)"
    >
      <CloseIcon /><span>删除当前项目</span>
    </button>
    <button
      v-if="['script', 'storyboard'].includes(route) && production"
      class="prompt-export-launcher"
      type="button"
      :disabled="exportingPackage"
      @click="exportProductionPackage"
    >
      <FileImportIcon /><span>{{
        exportingPackage ? "正在导出" : "一键导出剧本和分镜"
      }}</span>
    </button>
    <aside class="studio-sidebar">
      <div class="side-brand">
        <span class="brand-knot" aria-hidden="true"></span>
        <div><strong>饺子短剧</strong><small>导演创作台</small></div>
      </div>
      <div class="project-switcher" @click="setRoute('projects')">
        <span class="project-glyph"><FilmIcon /></span>
        <div>
          <small>当前项目</small
          ><strong>{{ currentProject?.title || "选择一个项目" }}</strong>
        </div>
        <ChevronDownIcon />
      </div>
      <nav class="main-nav">
        <button
          :class="{ active: route === 'projects' }"
          @click="setRoute('projects')"
        >
          <WalletIcon />项目库
        </button>
        <p>制作现场</p>
        <button
          :class="{ active: route === 'script' }"
          :disabled="!currentProject"
          @click="setRoute('script')"
        >
          <WriteIcon />剧本与章节</button
        ><button
          :class="{ active: route === 'assets' }"
          :disabled="!production"
          @click="setRoute('assets')"
        >
          <LayersIcon />角色 · 场景 · 道具</button
        ><button
          :class="{ active: route === 'storyboard' }"
          :disabled="!currentChapter"
          @click="setRoute('storyboard')"
        >
          <ViewListIcon />分镜时间线
        </button>
        <p>工作空间</p>
        <button @click="showSettings = true"><SettingIcon />模型与环境</button>
      </nav>
      <div class="side-bottom">
        <button class="profile-button" @click="logout">
          <span class="avatar">{{ user.username.slice(0, 1) }}</span
          ><span>{{ user.username }}</span
          ><LogoutIcon />
        </button>
      </div>
    </aside>
    <main class="studio-main">
      <header class="topbar">
        <div class="breadcrumbs">
          <span>项目库</span><ChevronDownIcon /><strong>{{
            currentProject?.title || "创作总览"
          }}</strong
          ><template v-if="currentChapter"
            ><ChevronDownIcon /><strong>{{
              currentChapter.title
            }}</strong></template
          >
        </div>
        <div class="top-actions">
          <span class="save-mark"><CheckCircleIcon /> 本地已保存</span
          ><button
            class="theme-toggle-launcher"
            type="button"
            :title="theme === 'dark' ? '切换至日间主题' : '切换至夜间主题'"
            @click="toggleTheme"
          >
            <SunnyIcon v-if="theme === 'dark'" /><MoonIcon v-else /></button
          ><button
            class="icon-button"
            title="设置"
            @click="showSettings = true"
          >
            <SettingIcon />
          </button>
        </div>
      </header>
      <div
        v-if="route !== 'projects' && currentProject"
        class="route-utility-bar"
      >
        <button
          class="exit-project-launcher"
          type="button"
          title="返回项目库"
          @click="exitProject"
        >
          <ChevronDownIcon /><span>退出项目</span>
        </button>
      </div>
      <section v-if="route === 'projects'" class="page-area overview-page">
        <div class="page-heading">
          <div>
            <span class="eyebrow">PROJECT LIBRARY / 01</span>
            <h1>你的故事现场</h1>
            <p>每一个项目都是一条从文字通向画面的生产线。</p>
          </div>
          <div class="library-actions">
            <t-button
              class="quick-create-button"
              theme="primary"
              @click="showQuickCreate = true"
              ><WriteIcon />一句话创作</t-button
            >
            <t-button
              class="new-project-button"
              variant="outline"
              @click="showCreateProject = true"
              ><AddIcon />新建项目</t-button
            >
          </div>
        </div>
        <div class="overview-ribbon">
          <div>
            <small>进行中的项目</small><strong>{{ projects.length }}</strong>
          </div>
          <div>
            <small>已提取镜头</small
            ><strong>{{
              projects.reduce((sum, item) => sum + item.shot_count, 0)
            }}</strong>
          </div>
          <div>
            <small>素材完成度</small
            ><strong
              >{{
                projects.length
                  ? Math.round(
                      (projects.reduce(
                        (sum, item) => sum + (item.shot_count ? 1 : 0),
                        0,
                      ) /
                        projects.length) *
                        100,
                    )
                  : 0
              }}%</strong
            >
          </div>
          <div class="ribbon-note">
            <TimeIcon /><span
              >最近活动<br /><b>{{
                projects[0]?.latest_chapter_title || "从第一个项目开始"
              }}</b></span
            >
          </div>
        </div>
        <div class="library-toolbar">
          <t-input v-model="search" placeholder="搜索项目名称" clearable
            ><template #prefix-icon><BrowseIcon /></template
          ></t-input>
          <button class="filter-button">最近更新 <ChevronDownIcon /></button>
        </div>
        <div v-if="filteredProjects.length" class="project-grid">
          <article
            v-for="project in filteredProjects"
            :key="project.id"
            class="project-tile"
            @click="openProject(project)"
          >
            <div class="tile-cover">
              <span>{{ project.genre }}</span>
              <div class="cover-lines"><i></i><i></i><i></i></div>
              <small>{{ project.aspect_ratio }}</small>
            </div>
            <div class="tile-body">
              <div>
                <h3>{{ project.title }}</h3>
                <p>{{ project.description || "还没有写下项目简介" }}</p>
              </div>
              <div class="tile-meta">
                <span>{{ project.chapter_count }} 章节</span
                ><span>{{ project.shot_count }} 镜头</span
                ><span class="status-dot" :class="project.status"></span>
              </div>
            </div>
            <button
              class="tile-delete-button"
              type="button"
              title="删除剧本"
              @click.stop="requestProjectDeletion(project)"
            >
              <DeleteIcon />
            </button>
          </article>
          <button
            class="project-tile new-tile"
            @click="showCreateProject = true"
          >
            <AddIcon /><span>建立新项目</span><small>从一个故事概念开始</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <FilmIcon />
          <h3>还没有项目</h3>
          <p>新建一个项目，把第一个故事放上时间线。</p>
          <t-button theme="primary" @click="showCreateProject = true"
            ><AddIcon />新建项目</t-button
          >
        </div>
      </section>
      <section v-else-if="route === 'script'" class="page-area workspace-page">
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >WRITING ROOM / {{ currentProject?.genre }}</span
            >
            <h1>{{ currentProject?.title }}</h1>
            <p>
              {{
                currentProject?.description ||
                "在这里把故事写成可以拍摄的章节。"
              }}
            </p>
          </div>
          <div class="heading-actions">
            <t-button variant="outline" @click="showCreateChapter = true"
              ><AddIcon />新章节</t-button
            ><t-button
              theme="primary"
              :loading="generating"
              @click="generateProduction"
              ><FilmIcon />生成制作包</t-button
            >
          </div>
        </div>
        <div class="work-layout">
          <aside class="chapter-rail">
            <div class="rail-title">
              <span>章节</span
              ><small
                >{{ currentProjectDetail?.chapters.length || 0 }} 集</small
              >
            </div>
            <button
              v-for="chapter in currentProjectDetail?.chapters"
              :key="chapter.id"
              class="chapter-item"
              :class="{ active: chapter.id === currentChapter?.id }"
              @click="selectChapter(chapter)"
            >
              <span class="chapter-no">{{
                String(chapter.episode_no).padStart(2, "0")
              }}</span
              ><span
                ><strong>{{ chapter.title }}</strong
                ><small>{{ statusLabel(chapter.status) }}</small></span
              ><CheckCircleIcon v-if="chapter.status === 'completed'" /></button
            ><button class="rail-add" @click="showCreateChapter = true">
              <AddIcon />添加章节
            </button>
          </aside>
          <div class="script-editor">
            <div class="editor-top">
              <div>
                <span class="eyebrow"
                  >EPISODE
                  {{
                    String(currentChapter?.episode_no || 1).padStart(2, "0")
                  }}</span
                ><input v-model="chapterDraft.title" class="title-input" />
              </div>
              <div class="editor-actions">
                <span v-if="currentChapter?.is_locked" class="locked"
                  ><LockOnIcon />已锁定</span
                ><t-button
                  variant="outline"
                  :loading="chapterSaving"
                  @click="saveChapter"
                  >保存章节</t-button
                ><t-button
                  theme="primary"
                  @click="setRoute('storyboard')"
                  :disabled="!currentChapter"
                  >查看分镜</t-button
                >
              </div>
            </div>
            <div class="editor-columns">
              <div>
                <label>本章梗概</label
                ><textarea
                  v-model="chapterDraft.outline"
                  class="outline-input"
                  placeholder="这集必须发生什么？情绪从哪里开始，到哪里结束？"
                ></textarea
                ><label>剧本正文</label
                ><textarea
                  v-model="chapterDraft.content"
                  class="script-input"
                  placeholder="场景：INT. 雨夜便利店 - 夜\n\n林默推门而入。玻璃门上的风铃轻响。\n\n林默（低声）：你果然在这里。"
                ></textarea>
              </div>
              <aside class="writing-guide">
                <span class="guide-mark">✦</span>
                <h3>导演提示</h3>
                <p>
                  把“发生了什么”写清楚，智能体会继续推断镜头语言、角色状态和可执行的动作节奏。
                </p>
                <div class="guide-line"></div>
                <small>支持 Word / PDF 导入<br />支持章节化持续创作</small
                ><button class="import-button">
                  <FileImportIcon />导入剧本
                </button>
              </aside>
            </div>
          </div>
        </div>
      </section>
      <section v-else-if="route === 'assets'" class="page-area workspace-page">
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >ASSET BIBLE /
              {{ production?.characters.length || 0 }} CHARACTERS</span
            >
            <h1>故事的视觉基因</h1>
            <p>实体从剧本中长出来，素材提示词保持同一套视觉风格。</p>
          </div>
        </div>
        <div class="asset-tabs">
          <button
            v-for="tab in [
              ['characters', '角色'],
              ['scenes', '场景'],
              ['props', '道具'],
            ] as const"
            :key="tab[0]"
            :class="{ active: assetTab === tab[0] }"
            @click="assetTab = tab[0]"
          >
            {{ tab[1] }} <span>{{ production?.[tab[0]].length || 0 }}</span>
          </button>
        </div>
        <div class="asset-grid">
          <article v-for="item in assets" :key="item.id" class="asset-card">
            <div class="asset-card-body">
              <div class="asset-card-content">
                <div class="asset-card-topline">
                  <span class="asset-id">{{ item.id }}</span>
                  <button
                    class="asset-action"
                    type="button"
                    title="编辑资产"
                    @click="openAssetEditor(item)"
                  >
                    <WriteIcon />
                  </button>
                </div>
                <h3>{{ item.name }}</h3>
                <template v-if="'appearance' in item"
                  ><p><b>身份</b>{{ item.role }}</p>
                  <p><b>外貌</b>{{ item.appearance }}</p>
                  <p><b>服装</b>{{ item.costume }}</p></template
                ><template v-else-if="'location' in item"
                  ><p><b>地点</b>{{ item.location }} · {{ item.time }}</p>
                  <p><b>光线</b>{{ item.lighting }}</p>
                  <p><b>空间</b>{{ item.layout }}</p></template
                ><template v-else
                  ><p><b>细节</b>{{ item.description }}</p>
                  <p><b>归属</b>{{ item.owner }}</p></template
                >
              </div>
            </div>
          </article>
        </div>
      </section>
      <section
        v-else-if="route === 'storyboard'"
        class="page-area storyboard-page"
      >
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >SHOT TIMELINE / {{ shots.length }} SHOTS</span
            >
            <h1>镜头时间线</h1>
            <p>从文字节拍到可生成画面，按秒检查每一次视觉转场。</p>
          </div>
          <div class="heading-actions">
            <div class="readiness">
              <span>制作就绪度</span><strong>{{ progress }}%</strong
              ><i><b :style="{ width: `${progress}%` }"></b></i>
            </div>
          </div>
        </div>
        <div class="timeline-wrap">
          <div class="timeline-ruler">
            <span v-for="n in 8" :key="n">{{ n - 1 }}s</span>
          </div>
          <div class="shot-track">
            <button
              v-for="shot in shots"
              :key="shot.id"
              class="shot-block"
              :class="{ active: activeShot?.id === shot.id }"
              :style="{
                width: `${Math.max(18, shot.duration_seconds * 34)}px`,
              }"
              @click="activeShot = shot"
            >
              <small>{{ shot.id.replace("shot_", "S") }}</small
              ><strong>{{ shot.shot_size || "镜头" }}</strong
              ><span>{{ shot.duration_seconds }}s</span>
            </button>
          </div>
        </div>
        <div class="storyboard-layout">
          <div class="shot-list">
            <article
              v-for="shot in shots"
              :key="shot.id"
              class="shot-row"
              :class="{ active: activeShot?.id === shot.id }"
              @click="activeShot = shot"
            >
              <div class="shot-meta">
                <strong>{{ shot.id.replace("shot_", "S") }}</strong>
                <span>{{ shot.start_second.toFixed(1) }}s</span>
              </div>
              <div class="shot-copy">
                <div class="shot-copy-head">
                  <strong
                    >{{ shot.shot_size }} · {{ shot.camera_motion }}</strong
                  ><span class="confidence">{{ shot.confidence }}</span
                  ><span class="shot-state shot-state-compact"
                    ><i :class="['state-ring', shot.status]"></i
                    >{{ statusLabel(shot.status) }}</span
                  >
                </div>
                <p>{{ shot.visual_action || "待补充动作描述" }}</p>
                <small>{{
                  shot.dialogue || "无对白 · " + (shot.sound_design || "环境声")
                }}</small>
              </div>
              <div class="shot-state">
                <span :class="['state-ring', shot.status]"></span
                ><span>{{ statusLabel(shot.status) }}</span>
              </div>
            </article>
          </div>
          <aside class="shot-inspector">
            <div v-if="activeShot">
              <div class="inspector-head">
                <div>
                  <span class="eyebrow">{{ activeShot.id }}</span>
                  <h2>
                    {{ activeShot.shot_size }} /
                    {{ activeShot.duration_seconds }} 秒
                  </h2>
                </div>
                <button
                  class="icon-button"
                  type="button"
                  title="编辑分镜提示词"
                  @click="openShotPromptEditor"
                ><WriteIcon /></button>
              </div>
              <div class="prompt-stack">
                <div class="prompt-title">
                  <span>核心动作</span><MoveIcon />
                </div>
                <p>{{ activeShot.visual_action }}</p>
                <div class="prompt-title">
                  <span>首帧提示词</span
                  ><button
                    type="button"
                    @click="copyPrompt(activeShot.first_frame_prompt)"
                  >
                    复制
                  </button>
                </div>
                <p class="prompt-text">
                  {{ activeShot.first_frame_prompt || "等待提示词生成" }}
                </p>
                <div class="prompt-title">
                  <span>视频提示词</span
                  ><button
                    type="button"
                    @click="copyPrompt(activeShot.video_prompt)"
                  >
                    复制
                  </button>
                </div>
                <p class="prompt-text">
                  {{ activeShot.video_prompt || "等待提示词生成" }}
                </p>
                <div class="prompt-title">
                  <span>尾帧提示词</span
                  ><button
                    type="button"
                    @click="copyPrompt(activeShot.last_frame_prompt)"
                  >
                    复制
                  </button>
                </div>
                <p class="prompt-text">
                  {{ activeShot.last_frame_prompt || "等待提示词生成" }}
                </p>
                <div class="prompt-title">
                  <span>负面提示词</span
                  ><button
                    type="button"
                    @click="copyPrompt(activeShot.negative_prompt)"
                  >
                    复制
                  </button>
                </div>
                <p class="prompt-text">
                  {{ activeShot.negative_prompt || "等待提示词生成" }}
                </p>
              </div>
            </div>
            <div v-else class="inspector-empty">
              <ViewListIcon />
              <p>
                {{
                  shots.length
                    ? "选择一个镜头\n检查它的生成协议"
                    : "当前章节还没有生成分镜\n先在剧本页点击“生成制作包”"
                }}
              </p>
            </div>
          </aside>
        </div>
      </section>
    </main>
    <t-dialog
      v-model:visible="showCreateProject"
      header="建立新项目"
      :footer="false"
      :destroy-on-close="true"
      :close-on-overlay-click="true"
      :close-on-esc-keydown="true"
      @close="closeCreateProject"
    >
      <t-form class="create-project-form" @submit="createProject">
        <t-form-item label="项目名称"
          ><t-input v-model="projectDraft.title" placeholder="例如：雨夜归来"
        /></t-form-item>
        <t-form-item label="题材"
          ><t-select
            v-model="projectDraft.genre"
            :options="genreOptions"
            filterable
            creatable
            placeholder="选择题材，或输入自定义题材"
            @create="setCustomProjectOption('genre', $event)"
        /></t-form-item>
        <t-form-item label="视觉风格"
          ><t-select
            v-model="projectDraft.style"
            :options="visualStyleOptions"
            filterable
            creatable
            placeholder="选择风格，或输入自定义风格"
            @create="setCustomProjectOption('style', $event)"
        /></t-form-item>
        <t-form-item label="项目简介"
          ><t-textarea v-model="projectDraft.description"
        /></t-form-item>
        <t-button
          theme="primary"
          type="submit"
          block
          :loading="projectCreating"
          :disabled="projectCreating"
          >建立项目</t-button
        >
      </t-form>
    </t-dialog>
    <t-dialog
      v-model:visible="showCreateChapter"
      header="新建章节"
      :footer="false"
      ><t-form class="create-chapter-form" @submit="createChapter"
        ><t-form-item label="章节标题"
          ><t-input
            v-model="chapterDraft.title"
            placeholder="例如：第 2 集 · 雨中的证词" /></t-form-item
        ><t-button theme="primary" type="submit" block
          >创建章节</t-button
        ></t-form
      ></t-dialog
    >
    <t-dialog
      v-model:visible="showDeleteProject"
      header="删除项目"
      :footer="false"
      :close-on-overlay-click="!deletingProject"
      :close-on-esc-keydown="!deletingProject"
    >
      <p class="project-delete-confirm">
        删除“{{
          projectPendingDeletion?.title
        }}”后，项目的章节、制作包和本地任务记录都会移除，无法恢复。
      </p>
      <div class="project-delete-actions">
        <t-button
          variant="outline"
          :disabled="deletingProject"
          @click="
            showDeleteProject = false;
            projectPendingDeletion = null;
          "
          >保留项目</t-button
        ><t-button
          theme="danger"
          :loading="deletingProject"
          @click="deleteProject"
          >确认删除</t-button
        >
      </div>
    </t-dialog>
    <t-dialog
      v-model:visible="showQuickCreate"
      header="一句话创作"
      :footer="false"
      :close-on-overlay-click="!quickCreating"
      :close-on-esc-keydown="!quickCreating"
    >
      <t-form @submit="createFromOneSentence">
        <section
          v-if="quickCreating || quickProgress.status !== 'idle'"
          class="quick-progress"
          aria-live="polite"
        >
          <div class="quick-progress-head">
            <strong>{{ quickProgress.stage }}</strong
            ><span>{{ Math.floor(quickProgress.percent) }}%</span>
          </div>
          <div class="quick-progress-track">
            <div
              class="quick-progress-fill"
              :class="{ failed: quickProgress.status === 'failed' }"
              :style="{ width: `${quickProgress.percent}%` }"
            ></div>
          </div>
          <p class="quick-progress-message">
            {{
              quickProgress.status === "failed"
                ? quickProgress.error || quickProgress.message
                : quickProgress.message
            }}
          </p>
          <div class="quick-progress-steps">
            <span :class="{ active: quickProgressTarget >= 15 }">项目</span
            ><span :class="{ active: quickProgressTarget >= 25 }">剧本</span
            ><span :class="{ active: quickProgressTarget >= 60 }"
              >资产与分镜</span
            >
          </div>
        </section>
        <t-form-item label="项目名称"
          ><t-input
            v-model="quickIdea.title"
            placeholder="可选，例如：雨夜便利店"
        /></t-form-item>
        <t-form-item label="一句话梗概"
          ><t-textarea
            v-model="quickIdea.brief"
            placeholder="例如：一个失忆的快递员在雨夜收到一封来自未来的信。"
            :autosize="{ minRows: 5, maxRows: 9 }"
        /></t-form-item>
        <p class="settings-hint">
          系统会自动生成完整剧本、制作包和分镜提示词，并支持分别导出剧本与全部提示词。
        </p>
        <t-button
          theme="primary"
          type="submit"
          block
          :loading="quickCreating"
          :disabled="quickCreating"
          ><WriteIcon />生成剧本与分镜</t-button
        >
      </t-form>
    </t-dialog>
    <t-dialog
      v-model:visible="showAssetEditor"
      :header="`编辑${editingAssetType === 'characters' ? '角色' : editingAssetType === 'scenes' ? '场景' : '道具'}`"
      :footer="false"
      width="640px"
      :close-on-overlay-click="!assetSaving"
      :close-on-esc-keydown="!assetSaving"
      @close="closeAssetEditor"
    >
      <t-form
        v-if="editingAsset"
        class="asset-editor-form"
        @submit="saveAsset"
      >
        <t-form-item label="名称">
          <t-input v-model="editingAsset.name" />
        </t-form-item>
        <template v-if="editingAssetType === 'characters'">
          <t-form-item label="身份">
            <t-input v-model="editingAsset.role" />
          </t-form-item>
          <t-form-item label="外貌">
            <t-textarea
              v-model="editingAsset.appearance"
              :autosize="{ minRows: 2, maxRows: 5 }"
            />
          </t-form-item>
          <t-form-item label="服装">
            <t-textarea
              v-model="editingAsset.costume"
              :autosize="{ minRows: 2, maxRows: 5 }"
            />
          </t-form-item>
          <t-form-item label="角色提示词">
            <t-textarea
              v-model="editingAsset.turnaround_prompt"
              :autosize="{ minRows: 3, maxRows: 7 }"
            />
          </t-form-item>
        </template>
        <template v-else-if="editingAssetType === 'scenes'">
          <div class="asset-editor-grid">
            <t-form-item label="地点">
              <t-input v-model="editingAsset.location" />
            </t-form-item>
            <t-form-item label="时间">
              <t-input v-model="editingAsset.time" />
            </t-form-item>
          </div>
          <t-form-item label="光线">
            <t-textarea
              v-model="editingAsset.lighting"
              :autosize="{ minRows: 2, maxRows: 5 }"
            />
          </t-form-item>
          <t-form-item label="空间布局">
            <t-textarea
              v-model="editingAsset.layout"
              :autosize="{ minRows: 2, maxRows: 5 }"
            />
          </t-form-item>
          <t-form-item label="场景提示词">
            <t-textarea
              v-model="editingAsset.environment_prompt"
              :autosize="{ minRows: 3, maxRows: 7 }"
            />
          </t-form-item>
        </template>
        <template v-else>
          <t-form-item label="细节">
            <t-textarea
              v-model="editingAsset.description"
              :autosize="{ minRows: 3, maxRows: 7 }"
            />
          </t-form-item>
          <t-form-item label="归属">
            <t-input v-model="editingAsset.owner" />
          </t-form-item>
        </template>
        <div class="asset-editor-actions">
          <t-button
            type="button"
            variant="outline"
            :disabled="assetSaving"
            @click="closeAssetEditor"
            >取消</t-button
          >
          <t-button
            type="submit"
            theme="primary"
            :loading="assetSaving"
            :disabled="assetSaving"
            >保存修改</t-button
          >
        </div>
      </t-form>
    </t-dialog>
    <t-dialog
      v-model:visible="showShotPromptEditor"
      header="编辑分镜提示词"
      :footer="false"
      width="720px"
      :close-on-overlay-click="!shotPromptSaving"
      :close-on-esc-keydown="!shotPromptSaving"
      @close="closeShotPromptEditor"
    >
      <t-form
        v-if="editingShotPrompts"
        class="asset-editor-form"
        @submit="saveShotPrompts"
      >
        <p class="shot-editor-id">{{ editingShotPrompts.id }}</p>
        <t-form-item label="首帧提示词">
          <t-textarea
            v-model="editingShotPrompts.first_frame_prompt"
            :autosize="{ minRows: 4, maxRows: 8 }"
          />
        </t-form-item>
        <t-form-item label="视频提示词">
          <t-textarea
            v-model="editingShotPrompts.video_prompt"
            :autosize="{ minRows: 4, maxRows: 8 }"
          />
        </t-form-item>
        <t-form-item label="尾帧提示词">
          <t-textarea
            v-model="editingShotPrompts.last_frame_prompt"
            :autosize="{ minRows: 4, maxRows: 8 }"
          />
        </t-form-item>
        <t-form-item label="负面提示词">
          <t-textarea
            v-model="editingShotPrompts.negative_prompt"
            :autosize="{ minRows: 3, maxRows: 6 }"
          />
        </t-form-item>
        <div class="asset-editor-actions">
          <t-button
            type="button"
            variant="outline"
            :disabled="shotPromptSaving"
            @click="closeShotPromptEditor"
            >取消</t-button
          >
          <t-button
            type="submit"
            theme="primary"
            :loading="shotPromptSaving"
            :disabled="shotPromptSaving"
            >保存修改</t-button
          >
        </div>
      </t-form>
    </t-dialog>
    <t-drawer
      v-model:visible="showSettings"
      header="模型配置中心"
      size="760px"
      :footer="false"
    >
      <div class="settings-drawer">
        <p class="settings-hint">
          配置保存在本机此应用中，不写入项目数据。API Key
          仅在连接测试或文本生成时发送，可在这里删除配置。
        </p>
        <div class="settings-tabs">
          <strong>文本模型</strong>
          <t-button theme="primary" size="small" @click="createConfig"
            ><AddIcon />新增配置</t-button
          >
        </div>
        <div class="config-center-layout">
          <div class="config-list">
            <article
              v-for="config in modelConfigCenter.text"
              :key="config.id"
              class="config-card"
              :class="{ active: editingConfigId === config.id }"
              @click="openConfigEditor(config)"
            >
              <div class="config-card-head">
                <div>
                  <strong>{{ config.name }}</strong
                  ><small>{{
                    config.mode === "cc_switch"
                      ? "CC-Switch"
                      : config.model || "手动接口"
                  }}</small>
                </div>
                <span class="config-state" :data-enabled="config.enabled">{{
                  config.enabled ? "启用" : "停用"
                }}</span>
              </div>
              <div v-if="config.is_default" class="config-card-meta">
                <span class="default-badge">默认</span>
              </div>
              <div class="config-card-actions">
                <button
                  type="button"
                  @click.stop="testProviderConnection(config)"
                >
                  测试连接
                </button>
                <button type="button" @click.stop="openConfigEditor(config)">
                  编辑
                </button>
                <button type="button" @click.stop="deleteConfig(config)">
                  删除
                </button>
              </div>
            </article>
            <div v-if="!modelConfigCenter.text.length" class="config-empty">
              <SettingIcon /><strong>还没有文本模型配置</strong>
              <p>新增一条配置后即可进行剧本和制作包生成。</p>
            </div>
          </div>
          <div v-if="editingConfig" class="config-editor">
            <div class="config-editor-head">
              <div>
                <span class="eyebrow">CONFIG EDITOR</span>
                <h3>{{ editingConfig.name }}</h3>
              </div>
              <button
                type="button"
                class="icon-button"
                @click="editingConfig = null"
              >
                <CloseIcon />
              </button>
            </div>
            <t-form class="config-editor-form">
              <t-form-item label="配置名称"
                ><t-input v-model="editingConfig.name"
              /></t-form-item>
              <t-form-item label="接口类型"
                ><t-select
                  v-model="editingConfig.mode"
                  :options="[
                    { label: 'OpenAI 兼容接口', value: 'manual' },
                    { label: 'CC-Switch', value: 'cc_switch' },
                  ]"
              /></t-form-item>
              <template v-if="editingConfig.mode === 'cc_switch'">
                <div class="runtime-card">
                  <p>
                    使用 CC-Switch
                    时，密钥由本机代理管理；饺子短剧只读取当前供应商和协议状态。
                  </p>
                  <div class="runtime-grid">
                    <div class="runtime-line">
                      <span>当前供应商</span
                      ><b>{{ ccSwitchRuntime.provider_name || "未检测到" }}</b>
                    </div>
                    <div class="runtime-line">
                      <span>当前模型</span
                      ><b>{{ ccSwitchRuntime.model || "未配置" }}</b>
                    </div>
                    <div class="runtime-line">
                      <span>当前协议</span
                      ><b>{{ ccSwitchRuntime.wire_api || "未知" }}</b>
                    </div>
                    <div class="runtime-line">
                      <span>代理状态</span><b>{{ ccSwitchStatusMessage }}</b>
                    </div>
                  </div>
                </div>
              </template>
              <template v-else>
                <t-form-item label="API Key"
                  ><t-input v-model="editingConfig.api_key" type="password"
                /></t-form-item>
                <t-form-item label="Base URL"
                  ><t-input v-model="editingConfig.base_url"
                /></t-form-item>
                <t-form-item label="模型"
                  ><t-input v-model="editingConfig.model"
                /></t-form-item>
                <t-form-item label="推理强度"
                  ><t-select
                    v-model="editingConfig.reasoning_effort"
                    :options="[
                      'auto',
                      'minimal',
                      'low',
                      'medium',
                      'high',
                      'xhigh',
                    ]"
                /></t-form-item>
              </template>
              <div class="config-runtime-settings">
                <div class="config-runtime-setting">
                  <span>启用状态</span>
                  <t-switch v-model="editingConfig.enabled" />
                </div>
              </div>
              <div class="config-editor-actions">
                <t-button
                  variant="outline"
                  @click="setDefaultConfig(editingConfig)"
                  >设为默认</t-button
                >
                <t-button
                  variant="outline"
                  :loading="modelTestBusy"
                  @click="testProviderConnection(editingConfig)"
                  >测试连接</t-button
                >
                <t-button theme="primary" @click="saveConfigEditor"
                  >保存配置</t-button
                >
              </div>
            </t-form>
          </div>
        </div>
        <div class="model-status" :data-state="modelStatus.state">
          <span></span>
          <p>{{ modelStatus.message }}</p>
        </div>
        <div class="settings-actions">
          <t-button variant="outline" @click="refreshRuntimeStatus"
            >刷新状态</t-button
          >
          <t-button theme="primary" @click="saveModelSettings"
            >关闭并保存</t-button
          >
        </div>
      </div>
    </t-drawer>
  </div>
</template>
