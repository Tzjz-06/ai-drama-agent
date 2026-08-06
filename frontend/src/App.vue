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
  ImageIcon,
  LayersIcon,
  LoadingIcon,
  LockOnIcon,
  LogoutIcon,
  MoonIcon,
  MoveIcon,
  PlayCircleIcon,
  SettingIcon,
  SoundIcon,
  SunnyIcon,
  TimeIcon,
  UserIcon,
  VideoIcon,
  ViewListIcon,
  WalletIcon,
  EditIcon as WriteIcon,
} from "tdesign-icons-vue-next";
import { MessagePlugin } from "tdesign-vue-next";
import {
  createProviderConfig,
  getActiveProvider,
  loadModelConfigCenter,
  mediaProviderOptions,
  mediaProviderPreset,
  toTaskProviderConfig,
  type MediaProviderConfig,
  type ModelConfigCenter,
  type ModelMode,
  type ProviderCategory,
  type ProviderConfig,
  type ProviderTaskConfig,
  type TextProviderConfig,
} from "./model-config";

type Route = "projects" | "script" | "assets" | "storyboard" | "export";
type AuthMode = "login" | "register";
type StudioTheme = "dark" | "light";

interface User { id: string; username: string; email: string; }
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
  id: string; title: string; description: string; style: string; genre: string;
  aspect_ratio: string; status: string; chapter_count: number; latest_chapter_title: string;
  character_count: number; scene_count: number; shot_count: number; updated_at: string;
}
interface Chapter {
  id: string; title: string; episode_no: number; outline: string; content: string;
  status: string; is_locked: boolean; production: Production | null;
}
interface Production {
  title: string; characters: Character[]; scenes: Scene[]; props: Prop[]; shots: Shot[];
  continuity_issues: ContinuityIssue[]; metadata?: Record<string, unknown>;
}
interface Character { id: string; name: string; role: string; appearance: string; costume: string; turnaround_prompt: string; status: string; }
interface Scene { id: string; name: string; location: string; time: string; lighting: string; environment_prompt: string; status: string; }
interface Prop { id: string; name: string; description: string; owner: string; }
interface ContinuityIssue { severity: string; scope: string; message: string; suggested_action: string; }
interface Shot {
  id: string; scene_id: string; character_ids: string[]; prop_ids: string[]; start_second: number;
  duration_seconds: number; shot_size: string; camera_position: string; lens: string;
  camera_motion: string; visual_action: string; dialogue: string; sound_design: string;
  first_frame_prompt: string; video_prompt: string; last_frame_prompt: string;
  negative_prompt: string; confidence: string; status: string;
}
interface Task { id: string; type: string; status: "queued" | "retrying" | "running" | "completed" | "failed" | "degraded" | "cancelled"; progress: number; message: string; shot_id?: string; result?: { url?: string }; }

const tokenKey = "jiaozi-auth-token";
const modelConfigKey = "jiaozi-model-config";
const modelConfigCenterKey = "jiaozi-model-config-center";
const themeKey = "jiaozi-studio-theme";
function readPersistentValue(key: string): string | null {
  return localStorage.getItem(key) || sessionStorage.getItem(key);
}
const theme = ref<StudioTheme>(localStorage.getItem(themeKey) === "light" ? "light" : "dark");
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
const search = ref("");
const loading = ref(false);
const generating = ref(false);
const chapterSaving = ref(false);
const tasks = ref<Task[]>([]);
const taskQueueError = ref("");
const showCreateProject = ref(false);
const showCreateChapter = ref(false);
const projectCreating = ref(false);
const deletingProject = ref(false);
const projectPendingDeletion = ref<ProjectSummary | null>(null);
const showDeleteProject = ref(false);
const importingScript = ref(false);
const scriptFileInput = ref<HTMLInputElement | null>(null);
const showTaskQueue = ref(false);
const showSettings = ref(false);
const cancellingTaskIds = ref<string[]>([]);
const deletingTaskIds = ref<string[]>([]);
const exportingPrompts = ref(false);
const showMediaPreview = ref(false);
const previewResultUrl = ref("");
const previewResultType = ref<"image" | "video">("image");
const activeFramePreviewUrl = ref("");
let activeFramePreviewRequest = 0;
const projectDraft = ref({ title: "", genre: "都市情感", style: "电影感二维国漫", aspect_ratio: "9:16", description: "" });
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
const settingsTab = ref<ProviderCategory>("text");
const editingConfigId = ref<string | null>(null);
const editingConfig = ref<ProviderConfig | null>(null);
const environmentModelConfigured = ref(false);
const environmentModel = ref("gpt-5.4");
const ccSwitchRuntime = ref<CCSwitchRuntime>(emptyCcSwitchRuntime());
const modelTestBusy = ref(false);
const modelStatus = ref<{ state: "idle" | "testing" | "success" | "error"; message: string }>({ state: "idle", message: "尚未测试当前配置" });
const activeTextConfig = computed(() => getActiveProvider(modelConfigCenter.value, "text") as TextProviderConfig | null);
const activeImageConfig = computed(() => getActiveProvider(modelConfigCenter.value, "image") as MediaProviderConfig | null);
const activeVideoConfig = computed(() => getActiveProvider(modelConfigCenter.value, "video") as MediaProviderConfig | null);
const isCcSwitchMode = computed(() => activeTextConfig.value?.mode === "cc_switch");
const ccSwitchReady = computed(() => (
  ccSwitchRuntime.value.available &&
  ccSwitchRuntime.value.proxy_enabled &&
  ccSwitchRuntime.value.proxy_running &&
  ["responses", "chat_completions", "chat-completions"].includes(ccSwitchRuntime.value.wire_api)
));
const ccSwitchStatusMessage = computed(() => {
  const runtime = ccSwitchRuntime.value;
  if (!runtime.available) return runtime.error || "未检测到 CC-Switch 运行态。";
  if (!runtime.proxy_enabled) return "CC-Switch Codex 代理未启用。";
  if (!runtime.proxy_running) return `CC-Switch 本地代理不可用（${runtime.proxy_status || "unavailable"}）。`;
  if (!["responses", "chat_completions", "chat-completions"].includes(runtime.wire_api)) {
    return `当前协议是 ${runtime.wire_api}，饺子短剧暂时不支持该协议。`;
  }
  return `CC-Switch 代理正常 · ${runtime.provider_name || "当前供应商"} · ${runtime.model || "未配置模型"} · ${runtime.wire_api}`;
});

const production = computed(() => currentChapter.value?.production || null);
const shots = computed(() => production.value?.shots || []);
const filteredProjects = computed(() => projects.value.filter((item) => item.title.toLowerCase().includes(search.value.toLowerCase())));
const assets = computed(() => production.value?.[assetTab.value] || []);
const progress = computed(() => {
  if (!production.value || shots.value.length === 0) return 0;
  const ready = shots.value.filter((shot) => shot.status === "confirmed").length;
  return Math.round((ready / shots.value.length) * 100);
});
const activeFrameTask = computed(() => tasks.value.find((task) => (
  task.type === "frame_image"
  && task.shot_id === activeShot.value?.id
  && task.status === "completed"
  && Boolean(task.result?.url)
)) || null);

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token.value) headers.set("Authorization", `Bearer ${token.value}`);
  const response = await fetch(path, { ...init, headers });
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error || `请求失败：HTTP ${response.status}`);
  return payload;
}

async function submitAuth(): Promise<void> {
  authBusy.value = true; authError.value = "";
  try {
    if (authMode.value === "login") {
      const result = await request<{ token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ identity: authForm.value.identity, password: authForm.value.password }) });
      token.value = result.token; user.value = result.user; localStorage.setItem(tokenKey, result.token); sessionStorage.removeItem(tokenKey); await loadProjects();
    } else {
      await request("/api/auth/register", { method: "POST", body: JSON.stringify({ username: authForm.value.username, email: authForm.value.email, password: authForm.value.password }) });
      authMode.value = "login"; authForm.value.identity = authForm.value.username; await submitAuth();
    }
  } catch (error) { authError.value = error instanceof Error ? error.message : "操作失败，请稍后重试。"; }
  finally { authBusy.value = false; }
}

async function loadProjects(): Promise<void> {
  const result = await request<{ projects: ProjectSummary[] }>("/api/projects");
  projects.value = result.projects;
  if (currentProject.value) {
    const refreshed = projects.value.find((item) => item.id === currentProject.value?.id);
    if (refreshed) currentProject.value = refreshed;
  }
}

async function openProject(project: ProjectSummary): Promise<void> {
  loading.value = true;
  try {
    const result = await request<{ project: ProjectSummary & { chapters: Chapter[] } }>(`/api/projects/${project.id}`);
    currentProject.value = result.project; currentProjectDetail.value = result.project;
    currentChapter.value = result.project.chapters[0] || null;
    if (currentChapter.value) setChapterDraft(currentChapter.value);
    await loadTasksForCurrentChapter();
    route.value = "script";
  } catch (error) { await showError(error); } finally { loading.value = false; }
}

function setChapterDraft(chapter: Chapter): void { chapterDraft.value = { title: chapter.title, outline: chapter.outline, content: chapter.content }; }
function selectChapter(chapter: Chapter): void {
  currentChapter.value = chapter;
  setChapterDraft(chapter);
  tasks.value = [];
  route.value = "script";
  void loadTasksForCurrentChapter();
}

async function loadTasksForCurrentChapter(): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId) {
    tasks.value = [];
    taskQueueError.value = "";
    return;
  }
  try {
    const result = await request<{ tasks: Task[] }>(`/api/projects/${projectId}/chapters/${chapterId}/tasks`);
    tasks.value = result.tasks;
    taskQueueError.value = "";
    for (const task of result.tasks) {
      if (task.status === "queued" || task.status === "retrying" || task.status === "running") void trackTask(task.id);
    }
  } catch (error) {
    tasks.value = [];
    taskQueueError.value = error instanceof Error ? error.message : "本地任务读取失败";
  }
}

async function createProject(): Promise<void> {
  if (projectCreating.value) return;
  projectCreating.value = true;
  try {
    const result = await request<{ project: ProjectSummary }>("/api/projects", { method: "POST", body: JSON.stringify(projectDraft.value) });
    projects.value.unshift(result.project);
    closeCreateProject();
    await openProject(result.project);
    projectDraft.value = { title: "", genre: "都市情感", style: "电影感二维国漫", aspect_ratio: "9:16", description: "" };
    await MessagePlugin.success("项目已建立");
  } catch (error) { await showError(error); }
  finally { projectCreating.value = false; }
}

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
      tasks.value = [];
      taskQueueError.value = "";
    }
    projectPendingDeletion.value = null;
    showDeleteProject.value = false;
    route.value = "projects";
    await MessagePlugin.success("项目及其本地任务已删除");
  } catch (error) { await showError(error); }
  finally { deletingProject.value = false; }
}

async function createChapter(): Promise<void> {
  if (!currentProject.value) return;
  try {
    const result = await request<{ chapter: Chapter }>(`/api/projects/${currentProject.value.id}/chapters`, { method: "POST", body: JSON.stringify({ title: chapterDraft.value.title || "新章节" }) });
    if (currentProjectDetail.value) currentProjectDetail.value.chapters.push(result.chapter);
    selectChapter(result.chapter); showCreateChapter.value = false; await MessagePlugin.success("章节已创建");
  } catch (error) { await showError(error); }
}

async function saveChapter(successMessage = "章节已保存"): Promise<boolean> {
  if (!currentProject.value || !currentChapter.value) return false;
  chapterSaving.value = true;
  try {
    const result = await request<{ chapter: Chapter }>(`/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}`, { method: "PATCH", body: JSON.stringify(chapterDraft.value) });
    currentChapter.value = result.chapter; if (currentProjectDetail.value) currentProjectDetail.value.chapters = currentProjectDetail.value.chapters.map((item) => item.id === result.chapter.id ? result.chapter : item); await MessagePlugin.success(successMessage);
    return true;
  } catch (error) { await showError(error); return false; } finally { chapterSaving.value = false; }
}

function chooseScriptFile(): void { scriptFileInput.value?.click(); }

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
      resolve(separator >= 0 ? reader.result.slice(separator + 1) : reader.result);
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
    const result = await request<{ script: string; filename: string; source_label: string }>("/api/import-script", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_base64: await encodeFileAsBase64(file),
        ocr_mode: "auto",
      }),
    });
    chapterDraft.value.content = result.script;
    await saveChapter(`已导入并保存 ${result.source_label}`);
  } catch (error) { await showError(error); } finally { importingScript.value = false; }
}

async function generateProduction(): Promise<void> {
  if (!currentProject.value || !currentChapter.value || !chapterDraft.value.content.trim()) { await MessagePlugin.warning("请先选择章节并录入剧本正文"); return; }
  const textConfig = activeTextConfig.value;
  if (textConfig?.mode === "cc_switch") {
    await refreshRuntimeStatus();
    if (!ccSwitchReady.value) {
      showSettings.value = true;
      modelStatus.value = { state: "error", message: ccSwitchStatusMessage.value };
      await MessagePlugin.warning(ccSwitchStatusMessage.value);
      return;
    }
  } else if (!textConfig && !environmentModelConfigured.value) {
    showSettings.value = true;
    await MessagePlugin.warning("请先添加并启用一个文本模型配置");
    return;
  } else if (textConfig && !textConfig.api_key && !environmentModelConfigured.value) {
    showSettings.value = true;
    await MessagePlugin.warning("请先配置并测试模型 API");
    return;
  }
  generating.value = true;
  try {
    await saveChapter();
    const result = await request<{ project: Production; chapter: Chapter }>(`/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/generate`, { method: "POST", body: JSON.stringify({ script: chapterDraft.value.content, style: currentProject.value.style, aspect_ratio: currentProject.value.aspect_ratio, fps: 24, target_model: "model-agnostic", model_config: textConfig || undefined }) });
    currentChapter.value = result.chapter; currentChapter.value.production = result.project; route.value = "storyboard"; activeShot.value = shots.value[0] || null; await loadProjects(); await MessagePlugin.success("实体与分镜已生成");
  } catch (error) { await showError(error); } finally { generating.value = false; }
}

async function queueTask(type: string, shot?: Shot): Promise<void> {
  if (!currentProject.value || !currentChapter.value) return;
  const body: { type: string; shot_id: string; prompt?: string; negative_prompt?: string; duration_seconds?: number; clips?: Array<{ path: string; duration: number }>; provider_config?: ProviderTaskConfig } = { type, shot_id: shot?.id || "" };
  if (type === "frame_image" || type === "asset_image" || type === "video") {
    const provider = type === "video" ? activeVideoConfig.value : activeImageConfig.value;
    if (!provider) {
      showSettings.value = true;
      await MessagePlugin.warning(type === "video" ? "请先添加并启用一个视频模型配置" : "请先添加并启用一个图片模型配置");
      return;
    }
    body.provider_config = toTaskProviderConfig(provider);
  }
  if (shot) {
    body.prompt = type === "frame_image" ? shot.first_frame_prompt : shot.video_prompt;
    body.negative_prompt = shot.negative_prompt;
    body.duration_seconds = shot.duration_seconds;
  }
  if (type === "merge") {
    body.clips = tasks.value.filter((task) => task.type === "video" && task.status === "completed" && task.result?.url).map((task) => ({ path: task.result?.url || "", duration: 0 }));
    if (!body.clips.length) { await MessagePlugin.warning("请先完成至少一个视频片段，再开始合成"); return; }
  }
  try {
    const result = await request<{ task: Task }>(`/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/tasks`, { method: "POST", body: JSON.stringify(body) });
    tasks.value.unshift(result.task); await MessagePlugin.info(result.task.message || "任务已加入队列"); void trackTask(result.task.id);
  } catch (error) { await showError(error); }
}

async function trackTask(taskId: string): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId) return;
  for (let attempt = 0; attempt < 240; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    try {
      const result = await request<{ task: Task }>(`/api/projects/${projectId}/chapters/${chapterId}/tasks/${taskId}`);
      tasks.value = tasks.value.map((task) => task.id === taskId ? result.task : task);
      if (["completed", "failed", "degraded", "cancelled"].includes(result.task.status)) return;
    } catch { return; }
  }
}

async function fetchTaskMedia(task: Task): Promise<string> {
  const resultUrl = task.result?.url;
  if (!resultUrl) throw new Error("任务没有可查看的结果文件。");
  const headers = new Headers();
  if (token.value) headers.set("Authorization", `Bearer ${token.value}`);
  const response = await fetch(resultUrl, { headers });
  if (!response.ok) throw new Error(`无法读取生成结果：HTTP ${response.status}`);
  return URL.createObjectURL(await response.blob());
}

async function previewTaskResult(task: Task): Promise<void> {
  try {
    const resultUrl = await fetchTaskMedia(task);
    URL.revokeObjectURL(previewResultUrl.value);
    previewResultUrl.value = resultUrl;
    previewResultType.value = task.type === "video" || task.type === "merge" ? "video" : "image";
    showMediaPreview.value = true;
  } catch (error) {
    await showError(error);
  }
}

function closeMediaPreview(): void {
  showMediaPreview.value = false;
  URL.revokeObjectURL(previewResultUrl.value);
  previewResultUrl.value = "";
}

async function refreshActiveFramePreview(task: Task | null): Promise<void> {
  const requestId = ++activeFramePreviewRequest;
  URL.revokeObjectURL(activeFramePreviewUrl.value);
  activeFramePreviewUrl.value = "";
  if (!task) return;
  try {
    const resultUrl = await fetchTaskMedia(task);
    if (requestId !== activeFramePreviewRequest) {
      URL.revokeObjectURL(resultUrl);
      return;
    }
    activeFramePreviewUrl.value = resultUrl;
  } catch {
    // The task record remains available even when its local media was removed.
  }
}

async function locateTaskShot(task: Task): Promise<void> {
  const shot = shots.value.find((item) => item.id === task.shot_id);
  if (!shot) {
    await MessagePlugin.warning("这个任务没有对应的分镜位置。");
    return;
  }
  activeShot.value = shot;
  route.value = "storyboard";
  showTaskQueue.value = false;
}

function canCancelTask(task: Task): boolean {
  return ["queued", "retrying", "running"].includes(task.status);
}

async function cancelTask(task: Task): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId || !canCancelTask(task) || cancellingTaskIds.value.includes(task.id)) return;
  cancellingTaskIds.value = [...cancellingTaskIds.value, task.id];
  try {
    const result = await request<{ task: Task }>(`/api/projects/${projectId}/chapters/${chapterId}/tasks/${task.id}/cancel`, { method: "POST", body: JSON.stringify({}) });
    tasks.value = tasks.value.map((item) => item.id === task.id ? result.task : item);
    await MessagePlugin.success("本地任务已取消");
  } catch (error) { await showError(error); }
  finally { cancellingTaskIds.value = cancellingTaskIds.value.filter((id) => id !== task.id); }
}

function canDeleteTask(task: Task): boolean {
  return ["completed", "failed", "degraded", "cancelled"].includes(task.status);
}

async function deleteTask(task: Task): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId || !canDeleteTask(task) || deletingTaskIds.value.includes(task.id)) return;
  deletingTaskIds.value = [...deletingTaskIds.value, task.id];
  try {
    await request(`/api/projects/${projectId}/chapters/${chapterId}/tasks/${task.id}`, { method: "DELETE" });
    tasks.value = tasks.value.filter((item) => item.id !== task.id);
    await MessagePlugin.success("任务记录已删除");
  } catch (error) { await showError(error); }
  finally { deletingTaskIds.value = deletingTaskIds.value.filter((id) => id !== task.id); }
}

async function queueAssetTasks(): Promise<void> {
  if (!currentProject.value || !currentChapter.value || !assets.value.length) return;
  const provider = activeImageConfig.value;
  if (!provider) {
    showSettings.value = true;
    await MessagePlugin.warning("请先添加并启用一个图片模型配置");
    return;
  }
  for (const item of assets.value) {
    const prompt = "turnaround_prompt" in item ? item.turnaround_prompt : "environment_prompt" in item ? item.environment_prompt : item.description;
    try {
      const result = await request<{ task: Task }>(`/api/projects/${currentProject.value.id}/chapters/${currentChapter.value.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({ type: "asset_image", shot_id: item.id, prompt, provider_config: toTaskProviderConfig(provider) }),
      });
      tasks.value.unshift(result.task);
      void trackTask(result.task.id);
    } catch (error) { await showError(error); return; }
  }
  await MessagePlugin.info(`${assets.value.length} 个素材任务已进入队列`);
}

async function showError(error: unknown): Promise<void> { await MessagePlugin.error(error instanceof Error ? error.message : "操作失败"); }
function closeCreateProject(): void { showCreateProject.value = false; }
function persistModelConfigCenter(): void {
  localStorage.setItem(modelConfigCenterKey, JSON.stringify(modelConfigCenter.value));
  sessionStorage.removeItem(modelConfigCenterKey);
  sessionStorage.removeItem(modelConfigKey);
}

function openConfigEditor(config: ProviderConfig): void {
  editingConfigId.value = config.id;
  editingConfig.value = { ...config };
}

function selectSettingsTab(category: ProviderCategory): void {
  settingsTab.value = category;
  const config = getActiveProvider(modelConfigCenter.value, category);
  if (config) {
    openConfigEditor(config);
  } else {
    editingConfigId.value = null;
    editingConfig.value = null;
  }
  resetModelStatus();
}

function createConfig(): void {
  const config = createProviderConfig(settingsTab.value);
  const list = modelConfigCenter.value[settingsTab.value];
  if (list.length === 0) config.is_default = true;
  list.push(config as never);
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

function applyMediaProviderPreset(config: MediaProviderConfig): void {
  const preset = mediaProviderPreset(config.category, config.provider);
  config.name = preset.defaultName;
  config.model = preset.defaultModel;
  if (!preset.requiresEndpoint) config.api_url = "";
}

async function testProviderConnection(config: ProviderConfig): Promise<void> {
  modelTestBusy.value = true;
  modelStatus.value = { state: "testing", message: `正在测试 ${config.name}...` };
  try {
    if (config.category === "text") {
      const result = await request<{ mode: ModelMode; model: string; provider: string; wire_api: string; elapsed_ms: number }>("/api/model/test", {
        method: "POST",
        body: JSON.stringify({ model_config: config }),
      });
      modelStatus.value = {
        state: "success",
        message: result.mode === "cc_switch"
          ? `连接成功 · ${result.provider || "CC-Switch"} · ${result.model} · ${result.wire_api} · ${result.elapsed_ms} ms`
          : `连接成功 · ${result.model} · ${result.elapsed_ms} ms`,
      };
    } else {
      const result = await request<{ model: string; status_code: number; elapsed_ms: number }>("/api/media/test", {
        method: "POST",
        body: JSON.stringify({ provider_config: config }),
      });
      modelStatus.value = {
        state: "success",
        message: `连接成功 · HTTP ${result.status_code} · ${result.model} · ${result.elapsed_ms} ms（未发起生成）`,
      };
    }
    persistModelConfigCenter();
  } catch (error) {
    modelStatus.value = { state: "error", message: error instanceof Error ? error.message : "连接测试失败" };
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
  modelStatus.value = { state: "testing", message: isCcSwitchMode.value ? "正在验证 CC-Switch 当前供应商与本地代理..." : "正在验证 API Key、Base URL 和模型..." };
  try {
    const result = await request<{ mode: ModelMode; model: string; base_url: string; provider: string; wire_api: string; elapsed_ms: number }>("/api/model/test", { method: "POST", body: JSON.stringify({ model_config: activeTextConfig.value || undefined }) });
    persistModelConfigCenter();
    modelStatus.value = {
      state: "success",
      message: result.mode === "cc_switch"
        ? `连接成功 · ${result.provider || "CC-Switch"} · ${result.model} · ${result.wire_api} · ${result.elapsed_ms} ms`
        : `连接成功 · ${result.model} · ${result.elapsed_ms} ms`,
    };
  } catch (error) {
    modelStatus.value = { state: "error", message: error instanceof Error ? error.message : "连接测试失败" };
  } finally { modelTestBusy.value = false; }
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
  tasks.value = [];
  taskQueueError.value = "";
  route.value = "projects";
}
function setRoute(next: Route): void { route.value = next; if (next === "storyboard") activeShot.value = shots.value[0] || null; }
async function copyPrompt(text: string): Promise<void> {
  if (!text.trim()) { await MessagePlugin.warning("当前没有可复制的提示词"); return; }
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else copyPromptWithFallback(text);
    await MessagePlugin.success("提示词已复制");
  } catch {
    try {
      copyPromptWithFallback(text);
      await MessagePlugin.success("提示词已复制");
    } catch (error) { await showError(error); }
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

async function exportPromptDocument(): Promise<void> {
  const projectId = currentProject.value?.id;
  const chapterId = currentChapter.value?.id;
  if (!projectId || !chapterId || !production.value || exportingPrompts.value) return;
  exportingPrompts.value = true;
  try {
    const response = await fetch(`/api/projects/${projectId}/chapters/${chapterId}/prompts.docx`, {
      headers: { Authorization: `Bearer ${token.value}` },
    });
    if (!response.ok) {
      const payload = await response.json() as { error?: string };
      throw new Error(payload.error || `导出失败：HTTP ${response.status}`);
    }
    const content = await response.blob();
    const url = URL.createObjectURL(content);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${currentProject.value?.title || "项目"}-${currentChapter.value?.title || "章节"}-全部提示词.docx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    await MessagePlugin.success("全部提示词 Word 文档已导出");
  } catch (error) { await showError(error); }
  finally { exportingPrompts.value = false; }
}
function taskLabel(type: string): string { return ({ frame_image: "关键帧", video: "视频片段", merge: "视频合成", asset_image: "资产素材" }[type] || type); }
function taskStatusLabel(value: Task["status"]): string {
  return ({ queued: "排队中", retrying: "重试中", running: "处理中", completed: "已完成", failed: "失败", degraded: "状态降级", cancelled: "已取消" }[value]);
}
function statusLabel(value: string): string { return ({ draft: "草稿", completed: "已完成", confirmed: "已锁定", "待确认": "待确认" }[value] || value); }

async function refreshRuntimeStatus(): Promise<void> {
  try {
    const runtime = await request<{ environment_model_configured: boolean; environment_model: string; cc_switch: CCSwitchRuntime }>("/api/runtime");
    environmentModelConfigured.value = runtime.environment_model_configured;
    environmentModel.value = runtime.environment_model;
    ccSwitchRuntime.value = runtime.cc_switch;
  } catch (error) {
    environmentModelConfigured.value = false;
    ccSwitchRuntime.value = {
      ...emptyCcSwitchRuntime(),
      error: error instanceof Error ? error.message : "运行态读取失败",
    };
  }
}

function resetModelStatus(): void {
  modelStatus.value = { state: "idle", message: isCcSwitchMode.value ? ccSwitchStatusMessage.value : "尚未测试当前配置" };
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

watch(() => activeTextConfig.value?.mode, () => {
  if (isCcSwitchMode.value) void refreshRuntimeStatus();
  resetModelStatus();
});

watch(activeFrameTask, (task) => {
  void refreshActiveFramePreview(task);
}, { immediate: true });

watch(showSettings, (visible) => {
  if (!visible) return;
  void refreshRuntimeStatus().then(() => {
    if (isCcSwitchMode.value) resetModelStatus();
  });
});

function openTaskQueue(): void { showTaskQueue.value = true; }
function openTaskQueueFromEvent(event: Event): void {
  const target = event.target;
  if (target instanceof Element && target.closest(".task-mini")) openTaskQueue();
}

onMounted(async () => {
  document.addEventListener("click", openTaskQueueFromEvent);
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
  try { const me = await request<{ user: User }>("/api/auth/me"); user.value = me.user; localStorage.setItem(tokenKey, token.value); sessionStorage.removeItem(tokenKey); await loadProjects(); } catch { logout(); }
});

onBeforeUnmount(() => {
  document.removeEventListener("click", openTaskQueueFromEvent);
  document.removeEventListener("click", handleImportButtonClick);
  scriptFileInput.value?.remove();
  scriptFileInput.value = null;
  URL.revokeObjectURL(previewResultUrl.value);
  URL.revokeObjectURL(activeFramePreviewUrl.value);
});
</script>

<template>
  <div v-if="!user" class="auth-shell" :class="{ 'theme-light': theme === 'light' }">
    <section class="auth-art"><div class="brand-lockup"><span class="logo-dumpling" aria-hidden="true"></span><span><strong>饺子短剧</strong><small>JIAOZI DRAMA STUDIO</small></span></div><p class="eyebrow">AI STORY PRODUCTION</p><h1>把一个故事，<br><em>做成一部短剧。</em></h1><p class="auth-lede">剧本、角色、场景、道具与逐镜提示词，在同一个创作流程里完成。</p><div class="auth-stamp"><span>导演创作台</span><span>01 / 04</span></div></section>
    <section class="auth-panel"><div class="auth-panel-top"><span class="mini-brand">饺子短剧</span><span>本地创作空间</span></div><div class="auth-form"><div class="auth-mode-tabs"><button :class="{ active: authMode === 'login' }" type="button" @click="authMode = 'login'">登录</button><button :class="{ active: authMode === 'register' }" type="button" @click="authMode = 'register'">注册</button></div><span class="eyebrow">CREATOR ACCESS</span><h2>{{ authMode === 'login' ? '继续你的创作' : '创建创作者账户' }}</h2><p>{{ authMode === 'login' ? '登录后进入项目管理台。' : '账户用于隔离这台设备上的项目数据。' }}</p><t-form @submit="submitAuth"><t-form-item v-if="authMode === 'register'" label="用户名"><t-input v-model="authForm.username" placeholder="你的创作者名称" /></t-form-item><t-form-item v-if="authMode === 'register'" label="邮箱"><t-input v-model="authForm.email" placeholder="可选" /></t-form-item><t-form-item v-else label="账号"><t-input v-model="authForm.identity" placeholder="用户名或邮箱" /></t-form-item><t-form-item label="密码"><t-input v-model="authForm.password" type="password" placeholder="至少 6 位字符" /></t-form-item><p v-if="authError" class="form-error">{{ authError }}</p><t-button theme="primary" block type="submit" :loading="authBusy">{{ authMode === 'login' ? '进入创作台' : '创建并进入' }} <ChevronDownIcon /></t-button></t-form></div><div class="auth-panel-foot"><span>你的内容只属于你的创作空间</span><LockOnIcon /></div></section>
  </div>
  <div v-else class="studio-shell" :class="{ 'theme-light': theme === 'light' }">
    <t-drawer v-model:visible="showTaskQueue" header="本地任务" size="460px">
      <div class="task-queue-panel">
        <div class="queue-summary">
          <span>当前章节任务</span>
          <strong>{{ tasks.length }} 个</strong>
        </div>
        <p v-if="taskQueueError" class="queue-error">{{ taskQueueError }}</p>
        <div v-if="tasks.length" class="queue-list">
          <article v-for="task in tasks" :key="task.id" class="queue-item">
            <div class="queue-item-icon">
              <LoadingIcon v-if="task.status === 'running'" />
              <CheckCircleIcon v-else-if="task.status === 'completed'" />
              <CloseIcon v-else-if="task.status === 'failed'" />
              <TimeIcon v-else />
            </div>
            <div class="queue-item-content">
              <div class="queue-item-heading">
                <strong>{{ taskLabel(task.type) }}</strong>
                <span :data-status="task.status">{{ taskStatusLabel(task.status) }}</span>
              </div>
              <p>{{ task.message || "等待本地执行器返回状态" }}</p>
              <div class="queue-progress"><i><b :style="{ width: `${Math.max(0, Math.min(100, task.progress))}%` }"></b></i><small>{{ task.progress }}%</small></div>
              <button v-if="task.shot_id" type="button" class="queue-item-id queue-shot-link" title="定位对应分镜" @click="locateTaskShot(task)">{{ task.shot_id }}</button>
              <small v-else class="queue-item-id">{{ task.id }}</small>
              <button v-if="task.result?.url" type="button" class="task-result-button" @click="previewTaskResult(task)">查看结果</button>
              <t-button v-if="canCancelTask(task)" class="queue-cancel-button" theme="danger" variant="outline" size="small" :loading="cancellingTaskIds.includes(task.id)" @click="cancelTask(task)">取消任务</t-button>
              <t-button v-if="canDeleteTask(task)" class="queue-delete-button" variant="text" size="small" :loading="deletingTaskIds.includes(task.id)" title="删除任务记录" @click="deleteTask(task)"><DeleteIcon />删除</t-button>
            </div>
          </article>
        </div>
        <div v-else class="queue-empty">
          <ViewListIcon />
          <strong>当前还没有任务</strong>
          <p>生成关键帧、视频或合成成片后，任务会显示在这里。</p>
        </div>
      </div>
    </t-drawer>
    <button v-if="route === 'projects' && currentProject" class="project-delete-launcher" type="button" title="删除当前项目" @click="requestProjectDeletion(currentProject)"><CloseIcon /><span>删除当前项目</span></button>
    <button v-if="route === 'storyboard' && production" class="prompt-export-launcher" type="button" :disabled="exportingPrompts" @click="exportPromptDocument"><FileImportIcon /><span>{{ exportingPrompts ? '正在导出' : '导出全部提示词' }}</span></button>
    <aside class="studio-sidebar"><div class="side-brand"><span class="brand-knot" aria-hidden="true"></span><div><strong>饺子短剧</strong><small>导演创作台</small></div></div><div class="project-switcher" @click="setRoute('projects')"><span class="project-glyph"><FilmIcon /></span><div><small>当前项目</small><strong>{{ currentProject?.title || '选择一个项目' }}</strong></div><ChevronDownIcon /></div><nav class="main-nav"><button :class="{ active: route === 'projects' }" @click="setRoute('projects')"><WalletIcon />项目库</button><p>制作现场</p><button :class="{ active: route === 'script' }" :disabled="!currentProject" @click="setRoute('script')"><WriteIcon />剧本与章节</button><button :class="{ active: route === 'assets' }" :disabled="!production" @click="setRoute('assets')"><LayersIcon />角色 · 场景 · 道具</button><button :class="{ active: route === 'storyboard' }" :disabled="!currentChapter" @click="setRoute('storyboard')"><ViewListIcon />分镜时间线</button><button :class="{ active: route === 'export' }" :disabled="!production" @click="setRoute('export')"><VideoIcon />成片合成</button><p>工作空间</p><button @click="showSettings = true"><SettingIcon />模型与环境</button></nav><div class="side-bottom"><div class="task-mini"><span class="live-dot"></span><div><strong>本地任务</strong><small>{{ tasks.length ? `${tasks.length} 个任务处理中` : '等待新的制作任务' }}</small></div><LoadingIcon v-if="tasks.some((task) => task.status === 'running')" /></div><button class="profile-button" @click="logout"><span class="avatar">{{ user.username.slice(0, 1) }}</span><span>{{ user.username }}</span><LogoutIcon /></button></div></aside>
    <main class="studio-main"><header class="topbar"><div class="breadcrumbs"><span>项目库</span><ChevronDownIcon /><strong>{{ currentProject?.title || '创作总览' }}</strong><template v-if="currentChapter"><ChevronDownIcon /><strong>{{ currentChapter.title }}</strong></template></div><div class="top-actions"><span class="save-mark"><CheckCircleIcon /> 本地已保存</span><button class="theme-toggle-launcher" type="button" :title="theme === 'dark' ? '切换至日间主题' : '切换至夜间主题'" @click="toggleTheme"><SunnyIcon v-if="theme === 'dark'" /><MoonIcon v-else /></button><button class="icon-button" title="设置" @click="showSettings = true"><SettingIcon /></button></div></header><div v-if="route !== 'projects' && currentProject" class="route-utility-bar"><button class="exit-project-launcher" type="button" title="返回项目库" @click="exitProject"><ChevronDownIcon /><span>退出项目</span></button></div>
      <section v-if="route === 'projects'" class="page-area overview-page">
        <div class="page-heading">
          <div>
            <span class="eyebrow">PROJECT LIBRARY / 01</span>
            <h1>你的故事现场</h1>
            <p>每一个项目都是一条从文字通向画面的生产线。</p>
          </div>
          <t-button theme="primary" @click="showCreateProject = true"><AddIcon />新建项目</t-button>
        </div>
        <div class="overview-ribbon">
          <div><small>进行中的项目</small><strong>{{ projects.length }}</strong></div>
          <div><small>已提取镜头</small><strong>{{ projects.reduce((sum, item) => sum + item.shot_count, 0) }}</strong></div>
          <div><small>素材完成度</small><strong>{{ projects.length ? Math.round(projects.reduce((sum, item) => sum + (item.shot_count ? 1 : 0), 0) / projects.length * 100) : 0 }}%</strong></div>
          <div class="ribbon-note"><TimeIcon /><span>最近活动<br><b>{{ projects[0]?.latest_chapter_title || '从第一个项目开始' }}</b></span></div>
        </div>
        <div class="library-toolbar">
          <t-input v-model="search" placeholder="搜索项目名称" clearable><template #prefix-icon><BrowseIcon /></template></t-input>
          <button class="filter-button">最近更新 <ChevronDownIcon /></button>
        </div>
        <div v-if="filteredProjects.length" class="project-grid">
          <article v-for="project in filteredProjects" :key="project.id" class="project-tile" @click="openProject(project)">
            <div class="tile-cover"><span>{{ project.genre }}</span><div class="cover-lines"><i></i><i></i><i></i></div><small>{{ project.aspect_ratio }}</small></div>
            <div class="tile-body"><div><h3>{{ project.title }}</h3><p>{{ project.description || '还没有写下项目简介' }}</p></div><div class="tile-meta"><span>{{ project.chapter_count }} 章节</span><span>{{ project.shot_count }} 镜头</span><span class="status-dot" :class="project.status"></span></div></div>
            <button class="tile-delete-button" type="button" title="删除剧本" @click.stop="requestProjectDeletion(project)"><DeleteIcon /></button>
          </article>
          <button class="project-tile new-tile" @click="showCreateProject = true"><AddIcon /><span>建立新项目</span><small>从一个故事概念开始</small></button>
        </div>
        <div v-else class="empty-state"><FilmIcon /><h3>还没有项目</h3><p>新建一个项目，把第一个故事放上时间线。</p><t-button theme="primary" @click="showCreateProject = true"><AddIcon />新建项目</t-button></div>
      </section>
      <section v-else-if="route === 'script'" class="page-area workspace-page"><div class="workspace-heading"><div><span class="eyebrow">WRITING ROOM / {{ currentProject?.genre }}</span><h1>{{ currentProject?.title }}</h1><p>{{ currentProject?.description || '在这里把故事写成可以拍摄的章节。' }}</p></div><div class="heading-actions"><t-button variant="outline" @click="showCreateChapter = true"><AddIcon />新章节</t-button><t-button theme="primary" :loading="generating" @click="generateProduction"><FilmIcon />生成制作包</t-button></div></div><div class="work-layout"><aside class="chapter-rail"><div class="rail-title"><span>章节</span><small>{{ currentProjectDetail?.chapters.length || 0 }} 集</small></div><button v-for="chapter in currentProjectDetail?.chapters" :key="chapter.id" class="chapter-item" :class="{ active: chapter.id === currentChapter?.id }" @click="selectChapter(chapter)"><span class="chapter-no">{{ String(chapter.episode_no).padStart(2, '0') }}</span><span><strong>{{ chapter.title }}</strong><small>{{ statusLabel(chapter.status) }}</small></span><CheckCircleIcon v-if="chapter.status === 'completed'" /></button><button class="rail-add" @click="showCreateChapter = true"><AddIcon />添加章节</button></aside><div class="script-editor"><div class="editor-top"><div><span class="eyebrow">EPISODE {{ String(currentChapter?.episode_no || 1).padStart(2, '0') }}</span><input v-model="chapterDraft.title" class="title-input" /></div><div class="editor-actions"><span v-if="currentChapter?.is_locked" class="locked"><LockOnIcon />已锁定</span><t-button variant="outline" :loading="chapterSaving" @click="saveChapter">保存章节</t-button><t-button theme="primary" @click="setRoute('storyboard')" :disabled="!currentChapter">查看分镜</t-button></div></div><div class="editor-columns"><div><label>本章梗概</label><textarea v-model="chapterDraft.outline" class="outline-input" placeholder="这集必须发生什么？情绪从哪里开始，到哪里结束？"></textarea><label>剧本正文</label><textarea v-model="chapterDraft.content" class="script-input" placeholder="场景：INT. 雨夜便利店 - 夜\n\n林默推门而入。玻璃门上的风铃轻响。\n\n林默（低声）：你果然在这里。"></textarea></div><aside class="writing-guide"><span class="guide-mark">✦</span><h3>导演提示</h3><p>把“发生了什么”写清楚，智能体会继续推断镜头语言、角色状态和可执行的动作节奏。</p><div class="guide-line"></div><small>支持 Word / PDF 导入<br>支持章节化持续创作</small><button class="import-button"><FileImportIcon />导入剧本</button></aside></div></div></div></section>
      <section v-else-if="route === 'assets'" class="page-area workspace-page"><div class="workspace-heading"><div><span class="eyebrow">ASSET BIBLE / {{ production?.characters.length || 0 }} CHARACTERS</span><h1>故事的视觉基因</h1><p>实体从剧本中长出来，素材提示词保持同一套风格锁定。</p></div><t-button theme="primary" @click="queueAssetTasks"><ImageIcon />批量生成素材</t-button></div><div class="asset-tabs"><button v-for="tab in ([['characters','角色'],['scenes','场景'],['props','道具']] as const)" :key="tab[0]" :class="{ active: assetTab === tab[0] }" @click="assetTab = tab[0]">{{ tab[1] }} <span>{{ production?.[tab[0]].length || 0 }}</span></button></div><div class="asset-grid"><article v-for="item in assets" :key="item.id" class="asset-card"><div class="asset-preview"><UserIcon v-if="assetTab === 'characters'" /><FilmIcon v-else-if="assetTab === 'scenes'" /><WalletIcon v-else /><span>{{ 'status' in item ? statusLabel(item.status) : '已提取' }}</span></div><div class="asset-card-body"><div><span class="asset-id">{{ item.id }}</span><h3>{{ item.name }}</h3><p>{{ 'appearance' in item ? item.appearance : 'location' in item ? item.location : item.description }}</p></div><button class="icon-button" title="查看提示词" @click="copyPrompt('turnaround_prompt' in item ? item.turnaround_prompt : 'environment_prompt' in item ? item.environment_prompt : item.description)"><WriteIcon /></button></div></article></div></section>
      <section v-else-if="route === 'storyboard'" class="page-area storyboard-page"><div class="workspace-heading"><div><span class="eyebrow">SHOT TIMELINE / {{ shots.length }} SHOTS</span><h1>镜头时间线</h1><p>从文字节拍到可生成画面，按秒检查每一次视觉转场。</p></div><div class="heading-actions"><div class="readiness"><span>制作就绪度</span><strong>{{ progress }}%</strong><i><b :style="{ width: `${progress}%` }"></b></i></div><t-button theme="primary" :disabled="!shots.length" @click="setRoute('export')"><VideoIcon />进入合成</t-button></div></div><div class="timeline-wrap"><div class="timeline-ruler"><span v-for="n in 8" :key="n">{{ n - 1 }}s</span></div><div class="shot-track"><button v-for="shot in shots" :key="shot.id" class="shot-block" :class="{ active: activeShot?.id === shot.id }" :style="{ width: `${Math.max(18, shot.duration_seconds * 34)}px` }" @click="activeShot = shot"><small>{{ shot.id.replace('shot_', 'S') }}</small><strong>{{ shot.shot_size || '镜头' }}</strong><span>{{ shot.duration_seconds }}s</span></button></div></div><div class="storyboard-layout"><div class="shot-list"><article v-for="shot in shots" :key="shot.id" class="shot-row" :class="{ active: activeShot?.id === shot.id }" @click="activeShot = shot"><div class="shot-number">{{ shot.id.replace('shot_', 'S') }}</div><div class="shot-thumb"><ImageIcon /><span>{{ shot.start_second.toFixed(1) }}s</span></div><div class="shot-copy"><div><strong>{{ shot.shot_size }} · {{ shot.camera_motion }}</strong><span class="confidence">{{ shot.confidence }}</span></div><p>{{ shot.visual_action || '待补充动作描述' }}</p><small>{{ shot.dialogue || '无对白 · ' + (shot.sound_design || '环境声') }}</small></div><div class="shot-state"><span :class="['state-ring', shot.status]"></span><span>{{ statusLabel(shot.status) }}</span></div></article></div><aside class="shot-inspector"><div v-if="activeShot"><div class="inspector-head"><div><span class="eyebrow">{{ activeShot.id }}</span><h2>{{ activeShot.shot_size }} / {{ activeShot.duration_seconds }} 秒</h2></div><button class="icon-button"><CloseIcon /></button></div><div class="inspector-media"><img v-if="activeFramePreviewUrl" :src="activeFramePreviewUrl" alt="当前镜头关键帧" /><template v-else><ImageIcon /><span>关键帧预览区域</span></template><button type="button" @click="queueTask('frame_image', activeShot)"><PlayCircleIcon />生成关键帧</button></div><div class="prompt-stack"><div class="prompt-title"><span>核心动作</span><MoveIcon /></div><p>{{ activeShot.visual_action }}</p><div class="prompt-title"><span>首帧提示词</span><button type="button" @click="copyPrompt(activeShot.first_frame_prompt)">复制</button></div><p class="prompt-text">{{ activeShot.first_frame_prompt || '等待提示词生成' }}</p><div class="prompt-title"><span>视频提示词</span><button type="button" @click="copyPrompt(activeShot.video_prompt)">复制</button></div><p class="prompt-text">{{ activeShot.video_prompt || '等待提示词生成' }}</p><div class="prompt-title"><span>尾帧提示词</span><button type="button" @click="copyPrompt(activeShot.last_frame_prompt)">复制</button></div><p class="prompt-text">{{ activeShot.last_frame_prompt || '等待提示词生成' }}</p><div class="prompt-title"><span>负面提示词</span><button type="button" @click="copyPrompt(activeShot.negative_prompt)">复制</button></div><p class="prompt-text">{{ activeShot.negative_prompt || '等待提示词生成' }}</p></div><div class="inspector-actions"><t-button variant="outline" @click="queueTask('frame_image', activeShot)"><ImageIcon />关键帧</t-button><t-button theme="primary" @click="queueTask('video', activeShot)"><VideoIcon />生成视频</t-button></div></div><div v-else class="inspector-empty"><ViewListIcon /><p>{{ shots.length ? '选择一个镜头\n检查它的生成协议' : '当前章节还没有生成分镜\n先在剧本页点击“生成制作包”' }}</p></div></aside></div></section>
      <section v-else class="page-area export-page"><div class="workspace-heading"><div><span class="eyebrow">FINAL ASSEMBLY / FFMPEG PIPELINE</span><h1>成片合成</h1><p>把完成的镜头片段按时间线合并，保留声音桥和镜头衔接契约。</p></div><t-button theme="primary" :disabled="!shots.length" @click="queueTask('merge')"><FilmIcon />开始合成</t-button></div><div class="export-grid"><div class="assembly-panel"><div class="assembly-head"><span>镜头片段</span><span>{{ shots.length }} 个镜头 · {{ shots.reduce((sum, shot) => sum + shot.duration_seconds, 0).toFixed(1) }} 秒</span></div><div v-for="shot in shots" :key="shot.id" class="assembly-row"><span class="state-ring" :class="shot.status"></span><strong>{{ shot.id.replace('shot_', '镜头 ') }}</strong><span>{{ shot.video_prompt ? '视频提示词就绪' : '等待视频任务' }}</span><small>{{ shot.duration_seconds }}s</small></div></div><div class="export-note"><SoundIcon /><h3>声音桥与转场</h3><p>合成任务会读取相邻镜头的衔接契约，保留环境声、对白和必要的桥接音效。</p><div class="technical-line"><span>编码</span><b>H.264 / AAC</b></div><div class="technical-line"><span>画幅</span><b>{{ currentProject?.aspect_ratio || '9:16' }}</b></div><div class="technical-line"><span>渲染器</span><b>本地 FFmpeg</b></div></div></div><div v-if="tasks.length" class="task-drawer"><div class="section-label"><span>最近任务</span><small>本地媒体执行</small></div><div v-for="task in tasks" :key="task.id" class="task-row"><LoadingIcon v-if="task.status === 'running'" /><CheckCircleIcon v-else /><div><strong>{{ taskLabel(task.type) }}</strong><small>{{ task.message }}</small></div><span>{{ task.status }}</span></div></div></section>
    </main>
    <t-dialog v-model:visible="showMediaPreview" header="生成结果" :footer="false" :destroy-on-close="true" @close="closeMediaPreview">
      <div class="media-preview-dialog">
        <img v-if="previewResultType === 'image' && previewResultUrl" :src="previewResultUrl" alt="生成结果" />
        <video v-else-if="previewResultUrl" :src="previewResultUrl" controls autoplay />
      </div>
    </t-dialog>
    <t-dialog v-model:visible="showCreateProject" header="建立新项目" :footer="false" :destroy-on-close="true" :close-on-overlay-click="true" :close-on-esc-keydown="true" @close="closeCreateProject">
      <t-form @submit="createProject">
        <t-form-item label="项目名称"><t-input v-model="projectDraft.title" placeholder="例如：雨夜归来" /></t-form-item>
        <t-form-item label="题材"><t-select v-model="projectDraft.genre" :options="['都市情感','悬疑','古风','科幻','喜剧']" /></t-form-item>
        <t-form-item label="视觉风格"><t-input v-model="projectDraft.style" /></t-form-item>
        <t-form-item label="项目简介"><t-textarea v-model="projectDraft.description" /></t-form-item>
        <t-button theme="primary" type="submit" block :loading="projectCreating" :disabled="projectCreating">建立项目</t-button>
      </t-form>
    </t-dialog>
    <t-dialog v-model:visible="showCreateChapter" header="新建章节" :footer="false"><t-form @submit="createChapter"><t-form-item label="章节标题"><t-input v-model="chapterDraft.title" placeholder="例如：第 2 集 · 雨中的证词" /></t-form-item><t-button theme="primary" type="submit" block>创建章节</t-button></t-form></t-dialog>
    <t-dialog v-model:visible="showDeleteProject" header="删除项目" :footer="false" :close-on-overlay-click="!deletingProject" :close-on-esc-keydown="!deletingProject">
      <p class="project-delete-confirm">删除“{{ projectPendingDeletion?.title }}”后，项目的章节、制作包和本地任务记录都会移除，无法恢复。</p>
      <div class="project-delete-actions"><t-button variant="outline" :disabled="deletingProject" @click="showDeleteProject = false; projectPendingDeletion = null">保留项目</t-button><t-button theme="danger" :loading="deletingProject" @click="deleteProject">确认删除</t-button></div>
    </t-dialog>
    <t-drawer v-model:visible="showSettings" header="模型配置中心" size="760px">
      <div class="settings-drawer">
        <p class="settings-hint">配置保存在本机此应用中，不写入项目数据。API Key 仅在连接测试或任务提交时发送，可在这里删除配置。</p>
        <div class="settings-tabs">
          <button v-for="tab in ([['text', '文本模型'], ['image', '图片模型'], ['video', '视频模型']] as const)" :key="tab[0]" type="button" :class="{ active: settingsTab === tab[0] }" @click="selectSettingsTab(tab[0])">{{ tab[1] }} <span>{{ modelConfigCenter[tab[0]].length }}</span></button>
          <t-button theme="primary" size="small" @click="createConfig"><AddIcon />新增配置</t-button>
        </div>
        <div class="config-center-layout">
          <div class="config-list">
            <article v-for="config in modelConfigCenter[settingsTab]" :key="config.id" class="config-card" :class="{ active: editingConfigId === config.id }" @click="openConfigEditor(config)">
              <div class="config-card-head">
                <div><strong>{{ config.name }}</strong><small>{{ config.category === 'text' ? (config.mode === 'cc_switch' ? 'CC-Switch' : config.model || '手动接口') : config.model || '未填写模型' }}</small></div>
                <span class="config-state" :data-enabled="config.enabled">{{ config.enabled ? '启用' : '停用' }}</span>
              </div>
              <div v-if="config.is_default" class="config-card-meta"><span class="default-badge">默认</span></div>
              <div class="config-card-actions">
                <button type="button" @click.stop="testProviderConnection(config)">测试连接</button>
                <button type="button" @click.stop="openConfigEditor(config)">编辑</button>
                <button type="button" @click.stop="deleteConfig(config)">删除</button>
              </div>
            </article>
            <div v-if="!modelConfigCenter[settingsTab].length" class="config-empty">
              <SettingIcon /><strong>还没有{{ settingsTab === 'text' ? '文本' : settingsTab === 'image' ? '图片' : '视频' }}配置</strong><p>新增一条配置后，任务才会有明确的上游服务。</p>
            </div>
          </div>
          <div v-if="editingConfig" class="config-editor">
            <div class="config-editor-head"><div><span class="eyebrow">CONFIG EDITOR</span><h3>{{ editingConfig.name }}</h3></div><button type="button" class="icon-button" @click="editingConfig = null"><CloseIcon /></button></div>
            <t-form class="config-editor-form">
              <t-form-item label="配置名称"><t-input v-model="editingConfig.name" /></t-form-item>
              <t-form-item v-if="editingConfig.category === 'text'" label="接口类型"><t-select v-model="editingConfig.mode" :options="[{ label: 'OpenAI 兼容接口', value: 'manual' }, { label: 'CC-Switch', value: 'cc_switch' }]" /></t-form-item>
              <template v-if="editingConfig.category === 'text' && editingConfig.mode === 'cc_switch'">
                <div class="runtime-card">
                  <p>使用 CC-Switch 时，密钥由本机代理管理；饺子短剧只读取当前供应商和协议状态。</p>
                  <div class="runtime-grid">
                    <div class="runtime-line"><span>当前供应商</span><b>{{ ccSwitchRuntime.provider_name || "未检测到" }}</b></div>
                    <div class="runtime-line"><span>当前模型</span><b>{{ ccSwitchRuntime.model || "未配置" }}</b></div>
                    <div class="runtime-line"><span>当前协议</span><b>{{ ccSwitchRuntime.wire_api || "未知" }}</b></div>
                    <div class="runtime-line"><span>代理状态</span><b>{{ ccSwitchStatusMessage }}</b></div>
                  </div>
                </div>
              </template>
              <template v-else-if="editingConfig.category === 'text'">
                <t-form-item label="API Key"><t-input v-model="editingConfig.api_key" type="password" /></t-form-item>
                <t-form-item label="Base URL"><t-input v-model="editingConfig.base_url" /></t-form-item>
                <t-form-item label="模型"><t-input v-model="editingConfig.model" /></t-form-item>
                <t-form-item label="推理强度"><t-select v-model="editingConfig.reasoning_effort" :options="['auto','minimal','low','medium','high','xhigh']" /></t-form-item>
              </template>
              <template v-else>
                <t-form-item label="服务商"><t-select v-model="editingConfig.provider" :options="mediaProviderOptions(editingConfig.category)" @change="applyMediaProviderPreset(editingConfig)" /></t-form-item>
                <t-form-item label="API Key"><t-input v-model="editingConfig.api_key" type="password" placeholder="粘贴你自己的 API Key" /></t-form-item>
                <t-form-item v-if="mediaProviderPreset(editingConfig.category, editingConfig.provider).requiresEndpoint" label="API 地址"><t-input v-model="editingConfig.api_url" placeholder="仅自建或兼容服务需要填写" /></t-form-item>
                <t-form-item label="模型"><t-input v-model="editingConfig.model" /></t-form-item>
              </template>
              <div class="config-runtime-settings">
                <div class="config-runtime-setting">
                  <span>启用状态</span>
                  <t-switch v-model="editingConfig.enabled" />
                </div>
              </div>
              <div class="config-editor-actions">
                <t-button variant="outline" @click="setDefaultConfig(editingConfig)">设为默认</t-button>
                <t-button variant="outline" :loading="modelTestBusy" @click="testProviderConnection(editingConfig)">测试连接</t-button>
                <t-button theme="primary" @click="saveConfigEditor">保存配置</t-button>
              </div>
            </t-form>
          </div>
        </div>
        <div class="model-status" :data-state="modelStatus.state"><span></span><p>{{ modelStatus.message }}</p></div>
        <div class="settings-actions">
          <t-button variant="outline" @click="refreshRuntimeStatus">刷新状态</t-button>
          <t-button theme="primary" @click="saveModelSettings">关闭并保存</t-button>
        </div>
      </div>
    </t-drawer>
  </div>
</template>
