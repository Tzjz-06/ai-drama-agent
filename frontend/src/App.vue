<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
type ProductMode = "drama" | "novel" | "jubensha";

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
  product_type?: ProductMode;
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
  novel_stage_count?: number;
  novel_word_count?: number;
  jubensha_role_count?: number;
  jubensha_clue_count?: number;
  jubensha_round_count?: number;
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
  production: Production | NovelPackage | JubenshaPackage | null;
}
interface Production {
  title: string;
  characters: Character[];
  scenes: Scene[];
  props: Prop[];
  shots: Shot[];
  material_map?: MaterialReference[];
  continuity_issues: ContinuityIssue[];
  metadata?: Record<string, unknown>;
}
interface MaterialReference {
  id: string;
  type: string;
  purpose: string;
}
interface NovelPackage {
  type: "novel_package";
  title: string;
  positioning: string;
  stages: string[];
  reader_contract?: Record<string, any>;
  opening_radar?: Record<string, any>;
  topic_report: Record<string, any>;
  world: Record<string, any>;
  characters: Record<string, any>[];
  outline: Record<string, any>;
  serial_plan?: Record<string, any>;
  chapter_title: string;
  chapter_outline: string;
  chapter_text: string;
  quality_gate?: Record<string, any>;
  style_pass?: string[];
  publish_gate?: Record<string, any>;
  review_report: Record<string, any>;
  polish_notes: string[];
  finalize: Record<string, any>;
  word_count: number;
  metadata?: Record<string, unknown>;
}
interface JubenshaPackage {
  type: "jubensha_package";
  title: string;
  positioning: string;
  stages: string[];
  play_contract: Record<string, any>;
  table_contract?: Record<string, any>;
  truth_spine: Record<string, any>;
  roles: Record<string, any>[];
  player_books?: Record<string, any>[];
  clues: Record<string, any>[];
  rounds: Record<string, any>[];
  dm_manual: Record<string, any>;
  props: Record<string, any>[];
  playability_gate: Record<string, any>;
  chapter_title: string;
  opening_script: string;
  full_script?: string;
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
interface PackageEditField {
  key: string;
  label: string;
  value: string;
  multiline?: boolean;
  lines?: boolean;
}
interface PackageEditContext {
  product: "novel" | "jubensha";
  target: string;
  index?: number;
  listKey?: "characters" | "outline.chapter_beats" | "player_books" | "roles" | "clues" | "rounds";
  sourceKey?: string;
  fieldSource?: Record<string, string>;
  title: string;
  fields: PackageEditField[];
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
  started_at?: number;
  elapsed_seconds?: number;
  estimated_seconds?: number;
  estimated_finish_at?: number;
}

const tokenKey = "jiaozi-auth-token";
const modelConfigKey = "jiaozi-model-config";
const modelConfigCenterKey = "jiaozi-model-config-center";
const themeKey = "jiaozi-studio-theme";
const productModeKey = "jiaozi-product-mode";
function readPersistentValue(key: string): string | null {
  return localStorage.getItem(key) || sessionStorage.getItem(key);
}
const theme = ref<StudioTheme>(
  localStorage.getItem(themeKey) === "light" ? "light" : "dark",
);
const productMode = ref<ProductMode>(
  ["drama", "novel", "jubensha"].includes(
    localStorage.getItem(productModeKey) || "",
  )
    ? (localStorage.getItem(productModeKey) as ProductMode)
    : "drama",
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
const novelAssetTab = ref<"theme" | "characters" | "scenes">("theme");
const jubenshaAssetTab = ref<"players" | "clues" | "rounds">("players");
const activeJubenshaReviewKey = ref("");
const activeNovelOutlineTab = ref("chapter");
const activeJubenshaReviewTab = ref("contract");
const showAssetEditor = ref(false);
const editingAsset = ref<AssetDraft | null>(null);
const editingAssetType = ref<"characters" | "scenes" | "props">("characters");
const assetSaving = ref(false);
const showPackageEditor = ref(false);
const packageEditContext = ref<PackageEditContext | null>(null);
const packageEditSaving = ref(false);
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
const showPackageProgress = ref(false);
const projectCreating = ref(false);
const chapterCreating = ref(false);
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
const chapterProgress = ref<QuickProgress>({
  status: "idle",
  percent: 0,
  stage: "等待续写",
  message: "提交后将显示续写阶段",
  error: "",
});
const chapterProgressTarget = ref(0);
let chapterProgressTimer: ReturnType<typeof setInterval> | null = null;
let chapterProgressAnimation: ReturnType<typeof setInterval> | null = null;

function clampProgressPercent(value: number | undefined): number {
  const percent = Number(value ?? 0);
  return Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;
}

function formatProgressDuration(seconds: number): string {
  const rounded = Math.max(0, Math.ceil(seconds));
  if (rounded < 60) return `${rounded}秒`;
  const minutes = Math.floor(rounded / 60);
  const remainder = rounded % 60;
  return remainder ? `${minutes}分${remainder}秒` : `${minutes}分钟`;
}

function progressTimingText(progress: QuickProgress): string {
  if (progress.elapsed_seconds === undefined) return "";
  if (progress.status === "completed") {
    return `实际用时 ${formatProgressDuration(progress.elapsed_seconds)}`;
  }
  if (progress.status === "failed") {
    return `已用时 ${formatProgressDuration(progress.elapsed_seconds)}`;
  }
  return "";
}

function startProgressAnimation(
  progressRef: { value: QuickProgress },
  fallbackEstimateSeconds = 60,
) {
  const localStartedAt = Date.now() / 1000;
  return setInterval(() => {
    const current = clampProgressPercent(progressRef.value.percent);
    if (progressRef.value.status === "failed") return;
    const completed = progressRef.value.status === "completed";
    const startedAt = Number(progressRef.value.started_at || localStartedAt);
    const elapsedFromClock = Math.max(0, Date.now() / 1000 - startedAt);
    const elapsedSeconds = Math.max(
      Number(progressRef.value.elapsed_seconds || 0),
      elapsedFromClock,
    );
    const estimatedSeconds = Math.max(
      Number(progressRef.value.estimated_seconds || fallbackEstimateSeconds),
      1,
    );
    const target = completed
      ? 100
      : Math.min(95, Math.max(1, (elapsedSeconds / estimatedSeconds) * 95));
    if (!completed && current >= target) {
      progressRef.value = {
        ...progressRef.value,
        elapsed_seconds: elapsedSeconds,
        estimated_seconds: estimatedSeconds,
      };
      return;
    }
    const nextPercent = completed
      ? Math.min(100, current + Math.max(1, Math.ceil((100 - current) / 8)))
      : target;
    progressRef.value = {
      ...progressRef.value,
      percent: nextPercent,
      elapsed_seconds: elapsedSeconds,
      estimated_seconds: estimatedSeconds,
    };
  }, 120);
}

function startPackageProgress(scope: ProductMode): {
  progressId: string;
  poll: () => Promise<void>;
  stop: () => void;
} {
  if (chapterProgressTimer) clearInterval(chapterProgressTimer);
  if (chapterProgressAnimation) clearInterval(chapterProgressAnimation);
  const progressId = crypto.randomUUID();
  chapterProgressTarget.value = 1;
  chapterProgress.value = {
    status: "running",
    percent: 0,
    stage: "准备制作包",
    message: "正在保存章节并校验生成条件",
    error: "",
  };
  showPackageProgress.value = true;
  const poll = async (): Promise<void> => {
    try {
      const result = await request<{ progress: QuickProgress }>(
        quickProgressPath(scope, progressId),
      );
      chapterProgressTarget.value = Math.max(
        chapterProgressTarget.value,
        clampProgressPercent(result.progress.percent),
      );
      chapterProgress.value = {
        ...result.progress,
        percent: chapterProgress.value.percent,
      };
    } catch {
      // The progress entry may not exist while the save request is in flight.
    }
  };
  chapterProgressAnimation = startProgressAnimation(
    chapterProgress,
    isNovelMode.value || isJubenshaMode.value ? 110 : 150,
  );
  chapterProgressTimer = setInterval(() => void poll(), 700);
  return {
    progressId,
    poll,
    stop: () => {
      if (chapterProgressTimer) clearInterval(chapterProgressTimer);
      if (chapterProgressAnimation) clearInterval(chapterProgressAnimation);
      chapterProgressTimer = null;
      chapterProgressAnimation = null;
    },
  };
}

async function completePackageProgress(stage: string, message: string): Promise<void> {
  chapterProgressTarget.value = 100;
  chapterProgress.value = {
    ...chapterProgress.value,
    status: "completed",
    stage,
    message,
    error: "",
  };
  await new Promise<void>((resolve) => {
    const waitForProgress = window.setInterval(() => {
      if (chapterProgress.value.percent >= 100) {
        window.clearInterval(waitForProgress);
        resolve();
      }
    }, 40);
  });
  await new Promise((resolve) => setTimeout(resolve, 450));
  showPackageProgress.value = false;
}

function resetPackageProgress(): void {
  if (generating.value) return;
  chapterProgress.value = {
    status: "idle",
    percent: 0,
    stage: "等待生成",
    message: "提交后将显示真实生成阶段",
    error: "",
  };
  chapterProgressTarget.value = 0;
}
const deletingProject = ref(false);
const projectPendingDeletion = ref<ProjectSummary | null>(null);
const showDeleteProject = ref(false);
const deletingChapter = ref(false);
const chapterPendingDeletion = ref<Chapter | null>(null);
const showDeleteChapter = ref(false);
const importingScript = ref(false);
const scriptFileInput = ref<HTMLInputElement | null>(null);
const showSettings = ref(false);
const exportingPackage = ref(false);
function defaultProjectDraft(mode: ProductMode) {
  if (mode === "novel") {
    return {
      product_type: "novel" as ProductMode,
      title: "",
      genre: "都市",
      style: "重生",
      aspect_ratio: "长篇连载",
      description: "",
    };
  }
  if (mode === "jubensha") {
    return {
      product_type: "jubensha" as ProductMode,
      title: "",
      genre: "还原本",
      style: "现代",
      aspect_ratio: "6人 / 4小时",
      description: "",
    };
  }
  return {
    product_type: "drama" as ProductMode,
    title: "",
    genre: "爱情甜宠短剧",
    style: "电影感二维国漫",
    aspect_ratio: "9:16",
    description: "",
  };
}
const projectDraft = ref(defaultProjectDraft(productMode.value));
type ProjectOption = { label: string; value: string };
function projectOptions(values: string[]): ProjectOption[] {
  return values.map((value) => ({ label: value, value }));
}
const genreOptionsByProduct = ref<Record<ProductMode, ProjectOption[]>>({
  drama: projectOptions([
    "爱情甜宠短剧",
    "悬疑推理短剧",
    "家庭伦理短剧",
    "职场励志短剧",
    "青春校园短剧",
    "穿越题材短剧",
    "历史题材短剧",
    "科幻题材短剧",
    "美食烹饪短剧",
    "互动剧情短剧",
  ]),
  novel: projectOptions([
    "都市",
    "都市生活",
    "现代言情",
    "古代言情",
    "玄幻",
    "科幻",
    "悬疑",
    "历史",
    "体育",
    "武侠",
    "文学小说",
    "游戏动漫",
  ]),
  jubensha: projectOptions([
    "推理本",
    "欢乐本",
    "情感本",
    "演绎本",
    "机制阵营本",
    "还原本",
  ]),
});
const visualStyleOptionsByProduct = ref<Record<ProductMode, ProjectOption[]>>({
  drama: projectOptions([
    "电影感二维国漫",
    "写实电影感",
    "电影级三渲二",
    "新中式水墨",
    "日系动画",
    "复古港风",
    "赛博朋克",
    "黑白漫画",
  ]),
  novel: projectOptions([
    "校园",
    "海岛",
    "大唐",
    "盗墓",
    "鉴宝",
    "空间",
    "宠物",
    "虐文",
    "系统",
    "推理",
    "外卖",
    "甜宠",
    "神豪",
    "洪荒",
    "清穿",
    "灵异",
    "种田",
    "三国",
    "星际",
    "无限流",
    "快穿",
    "末世",
    "美食",
    "娱乐圈",
    "重生",
    "直播",
    "年代",
    "二次元",
    "穿越",
    "兽世",
    "剑道",
    "诸天万界",
  ]),
  jubensha: projectOptions([
    "古代",
    "近代",
    "现代",
    "未来",
    "架空",
    "中式",
    "西方",
    "日式",
  ]),
});
const genreOptions = computed(() => genreOptionsByProduct.value[productMode.value]);
const visualStyleOptions = computed(
  () => visualStyleOptionsByProduct.value[productMode.value],
);
const quickIdea = ref({ title: "", brief: "" });
const quickDramaGenreOptions = computed(() => genreOptionsByProduct.value.drama);
const quickDramaStyleOptions = computed(
  () => visualStyleOptionsByProduct.value.drama,
);
const quickNovelGenreOptions = computed(() => genreOptionsByProduct.value.novel);
const quickNovelStyleOptions = computed(
  () => visualStyleOptionsByProduct.value.novel,
);
const quickJubenshaGenreOptions = computed(
  () => genreOptionsByProduct.value.jubensha,
);
const quickJubenshaStyleOptions = computed(
  () => visualStyleOptionsByProduct.value.jubensha,
);
const quickJubenshaPlayerCountOptions = projectOptions([
  "4人",
  "5人",
  "6人",
  "7人",
  "8人",
]);
const quickJubenshaDurationOptions = projectOptions([
  "2小时",
  "3小时",
  "4小时",
  "5小时",
  "6小时",
  "7小时",
  "8小时",
  "9小时",
  "10小时",
  "11小时",
  "12小时",
]);
function defaultQuickDramaForm() {
  return {
    genre: "爱情甜宠短剧",
    style: "电影感二维国漫",
  };
}
function defaultQuickNovelForm() {
  return {
    genre: "都市",
    style: "重生",
  };
}
function defaultQuickJubenshaForm() {
  return {
    genre: "还原本",
    style: "现代",
    player_count: "6人",
    duration: "4小时",
  };
}
const quickDramaForm = ref(defaultQuickDramaForm());
const quickNovelForm = ref(defaultQuickNovelForm());
const quickJubenshaForm = ref(defaultQuickJubenshaForm());
const quickCreateTitleMaxLength = computed(() =>
  isNovelMode.value ? 24 : isJubenshaMode.value ? 24 : 20,
);
const quickCreateBriefMaxLength = computed(() =>
  isNovelMode.value ? 180 : isJubenshaMode.value ? 120 : 140,
);
const projectGenreLabel = computed(() =>
  isNovelMode.value ? "主题" : isJubenshaMode.value ? "剧本类型" : "题材",
);
const projectStyleLabel = computed(() =>
  isNovelMode.value ? "情节标签" : isJubenshaMode.value ? "故事底色" : "视觉风格",
);
const chapterDraft = ref({ title: "", outline: "", content: "" });
const newChapterForm = ref({ title: "", brief: "" });
const newChapterEpisodeNo = ref(1);
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
document.documentElement.dataset.productMode = productMode.value;
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
const appVersion = ref("0.4.3");
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
    return `当前协议是 ${runtime.wire_api}，${productName.value}暂时不支持该协议。`;
  }
  return `CC-Switch 代理正常 · ${runtime.provider_name || "当前供应商"} · ${runtime.model || "未配置模型"} · ${runtime.wire_api}`;
});

const isNovelMode = computed(() => productMode.value === "novel");
const isJubenshaMode = computed(() => productMode.value === "jubensha");
const productName = computed(() =>
  isNovelMode.value
    ? "饺子网文"
    : isJubenshaMode.value
      ? "饺子剧本杀"
      : "饺子短剧",
);
const productSubtitle = computed(() =>
  isNovelMode.value
    ? "长篇创作台"
    : isJubenshaMode.value
      ? "开本创作台"
      : "导演创作台",
);
const productIndex = computed(() =>
  isNovelMode.value ? "02" : isJubenshaMode.value ? "03" : "01",
);
const chapterUnitLabel = computed(() =>
  isNovelMode.value ? "章" : isJubenshaMode.value ? "幕" : "集",
);
const libraryTitle = computed(() =>
  isNovelMode.value
    ? "你的连载书架"
    : isJubenshaMode.value
      ? "你的开本档案"
      : "你的故事现场",
);
const libraryDescription = computed(() =>
  isNovelMode.value
    ? "每一本书沿着设定、章节、追读钩子和连载发布持续推进。"
    : isJubenshaMode.value
      ? "每一个本都沿着定位、席位、线索、轮次和 DM 复盘推进。"
      : "每一个项目都是一条从文字通向画面的生产线。",
);
const workflowLabel = computed(() =>
  isNovelMode.value ? "创作流程" : isJubenshaMode.value ? "开本流程" : "制作现场",
);
const firstNavLabel = computed(() =>
  isNovelMode.value ? "章节写作" : isJubenshaMode.value ? "开本写作" : "剧本与章节",
);
const secondNavLabel = computed(() =>
  isNovelMode.value
    ? "作品设定"
    : isJubenshaMode.value
      ? "玩家本"
      : "角色 · 场景 · 道具",
);
const thirdNavLabel = computed(() =>
  isNovelMode.value ? "大纲追更" : isJubenshaMode.value ? "复盘质检" : "分镜时间线",
);
const quickCreateLabel = computed(() =>
  isNovelMode.value ? "一句话写书" : isJubenshaMode.value ? "一句话开本" : "一句话创作",
);
const packageButtonLabel = computed(() =>
  isNovelMode.value
    ? "生成连载方案"
    : isJubenshaMode.value
      ? "生成开本制作包"
      : "生成制作包",
);
const exportLauncherVisible = computed(
  () => route.value !== "projects" && Boolean(production.value),
);
const exportLauncherLabel = computed(() =>
  "一键导出资源包",
);
const exportLauncherSuccessLabel = computed(() =>
  "资源包已一键导出",
);
const productNoun = computed(() =>
  isNovelMode.value ? "作品" : isJubenshaMode.value ? "本" : "项目",
);
const production = computed(() => currentChapter.value?.production || null);
const dramaProduction = computed<Production | null>(() =>
  production.value &&
  !(
    "type" in production.value &&
    ["novel_package", "jubensha_package"].includes(String(production.value.type))
  )
    ? (production.value as Production)
    : null,
);
const novelPackage = computed<NovelPackage | null>(() =>
  production.value && "type" in production.value && production.value.type === "novel_package"
    ? (production.value as NovelPackage)
    : null,
);
const novelChapterBody = computed(() => {
  const text = (novelPackage.value?.chapter_text || chapterDraft.value.content).trim();
  const title = novelPackage.value?.chapter_title.trim();
  return title && text.startsWith(title) ? text.slice(title.length).trimStart() : text;
});
const novelSerialChecks = computed(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  const radar = packageData.opening_radar || {};
  const serialPlan = packageData.serial_plan || {};
  const qualityGate = packageData.quality_gate || packageData.review_report || {};
  const publishGate = packageData.publish_gate || packageData.finalize || {};
  const fixes = Array.isArray(qualityGate.fixes)
    ? qualityGate.fixes
    : qualityGate;
  return [
    { label: "本章钩子", detail: toReadableText(radar.chapter_1_hook) },
    { label: "下一章推进", detail: toReadableText(radar.chapter_2_push) },
    { label: "追读兑现", detail: toReadableText(radar.chapter_3_payoff) },
    { label: "更新节奏", detail: toReadableText(serialPlan.update_unit) },
    {
      label: "发布检查",
      detail: `${packageData.word_count} 字 · ${toReadableText(publishGate.platform_format || fixes)}`,
    },
  ];
});
const novelWritingStats = computed(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  return [
    { label: "当前章名", value: chapterDraft.value.title || currentChapter.value?.title || "待填写" },
    { label: "本章方向", value: chapterDraft.value.outline || "待填写" },
    { label: "正文长度", value: `${chapterDraft.value.content.trim().length} 字` },
    { label: "连载钩子", value: toReadableText(packageData.opening_radar?.chapter_3_payoff) },
  ];
});
const jubenshaWritingStats = computed(() => {
  const packageData = jubenshaPackage.value;
  return [
    { label: "当前幕名", value: chapterDraft.value.title || currentChapter.value?.title || "待填写" },
    { label: "本幕方向", value: chapterDraft.value.outline || "待填写" },
    { label: "正文长度", value: `${chapterDraft.value.content.trim().length} 字` },
    {
      label: "开局钩子",
      value: toReadableText(
        packageData?.truth_spine?.opening_question || packageData?.play_contract?.main_hook,
      ),
    },
  ];
});
const jubenshaPackage = computed<JubenshaPackage | null>(() =>
  production.value && "type" in production.value && production.value.type === "jubensha_package"
    ? (production.value as JubenshaPackage)
    : null,
);
const shots = computed(() => dramaProduction.value?.shots || []);
const nextEpisodeNo = computed(() => {
  const chapters = currentProjectDetail.value?.chapters || [];
  return Math.max(0, ...chapters.map((chapter) => chapter.episode_no)) + 1;
});
const filteredProjects = computed(() =>
  projects.value.filter((item) => {
    const itemType = item.product_type || "drama";
    return (
      itemType === productMode.value &&
      item.title.toLowerCase().includes(search.value.toLowerCase())
    );
  }),
);
const assets = computed(() => dramaProduction.value?.[assetTab.value] || []);

function assetKind(item: Asset): "人物" | "场景" | "道具" {
  if ("appearance" in item) return "人物";
  if ("location" in item) return "场景";
  return "道具";
}

function assetIdentity(item: Asset): string {
  return `${assetKind(item)}资产：${item.name}（编号 ${item.id}）`;
}

function assetReferenceLabel(item: Asset): string {
  const exists = (dramaProduction.value?.material_map || []).some(
    (material) => material.id === item.id,
  );
  return exists
    ? `${item.id}（分镜直接引用此编号）`
    : `${item.id}（资产编号）`;
}
const progress = computed(() => {
  if (!dramaProduction.value || shots.value.length === 0) return 0;
  const ready = shots.value.filter(
    (shot) => shot.status === "confirmed",
  ).length;
  return Math.round((ready / shots.value.length) * 100);
});
function projectGeneratedCount(item: ProjectSummary): number {
  if (isNovelMode.value) return item.novel_stage_count || 0;
  if (isJubenshaMode.value) return item.jubensha_clue_count || 0;
  return item.shot_count;
}
function projectIsPackaged(item: ProjectSummary): boolean {
  if (isNovelMode.value) return Boolean(item.novel_stage_count);
  if (isJubenshaMode.value) return Boolean(item.jubensha_round_count);
  return Boolean(item.shot_count);
}
function projectMetricText(item: ProjectSummary): string {
  if (isNovelMode.value) return `${item.novel_word_count || 0} 字`;
  if (isJubenshaMode.value)
    return `${item.jubensha_role_count || 0} 角色 · ${item.jubensha_clue_count || 0} 线索`;
  return `${item.shot_count} 镜头`;
}
function productClassMap() {
  return {
    "theme-light": theme.value === "light",
    "product-novel": isNovelMode.value,
    "product-jubensha": isJubenshaMode.value,
  };
}

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
    if (currentChapter.value) {
      setChapterDraft(currentChapter.value);
    } else {
      resetChapterDraft();
    }
    activeShot.value = null;
    route.value = "script";
  } catch (error) {
    await showError(error);
  } finally {
    loading.value = false;
  }
}

function resetChapterDraft(): void {
  chapterDraft.value = { title: "", outline: "", content: "" };
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

function setProductMode(mode: ProductMode): void {
  if (productMode.value === mode) return;
  productMode.value = mode;
  localStorage.setItem(productModeKey, mode);
  document.documentElement.dataset.productMode = mode;
  projectDraft.value = defaultProjectDraft(mode);
  quickDramaForm.value = defaultQuickDramaForm();
  quickNovelForm.value = defaultQuickNovelForm();
  quickJubenshaForm.value = defaultQuickJubenshaForm();
  exitProject();
}

function quickCreatePath(mode: ProductMode): string {
  return `/api/${mode}/quick-create`;
}

function quickProgressPath(mode: ProductMode, progressId: string): string {
  return `/api/${mode}/progress/${progressId}`;
}

function chapterGeneratePath(
  mode: ProductMode,
  projectId: string,
  chapterId: string,
): string {
  return `/api/${mode}/projects/${projectId}/chapters/${chapterId}/generate`;
}

async function createProject(): Promise<void> {
  if (projectCreating.value) return;
  projectCreating.value = true;
  try {
    const result = await request<{ project: ProjectSummary }>("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        ...projectDraft.value,
        product_type: productMode.value,
      }),
    });
    projects.value.unshift(result.project);
    closeCreateProject();
    await openProject(result.project);
    projectDraft.value = defaultProjectDraft(productMode.value);
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
  const title = quickIdea.value.title.trim();
  if (!brief) {
    await MessagePlugin.warning("请先写下一句话梗概或故事想法");
    return;
  }
  if (title.length > quickCreateTitleMaxLength.value) {
    await MessagePlugin.warning(`项目名称最多 ${quickCreateTitleMaxLength.value} 字`);
    return;
  }
  if (brief.length > quickCreateBriefMaxLength.value) {
    await MessagePlugin.warning(`一句话内容最多 ${quickCreateBriefMaxLength.value} 字`);
    return;
  }
  if (isNovelMode.value) {
    await createNovelFromOneSentence(brief);
    return;
  }
  if (isJubenshaMode.value) {
    await createJubenshaFromOneSentence(brief);
    return;
  }
  if (quickCreating.value || !(await ensureTextModelReady())) return;
  quickCreating.value = true;
  const progressId = crypto.randomUUID();
  quickProgressTarget.value = 1;
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
        quickProgressPath("drama", progressId),
      );
      quickProgressTarget.value = Math.max(
        quickProgressTarget.value,
        clampProgressPercent(result.progress.percent),
      );
      quickProgress.value = {
        ...result.progress,
        percent: quickProgress.value.percent,
      };
    } catch {
      // The progress entry may not exist during the first request round trip.
    }
  };
  quickProgressAnimation = startProgressAnimation(
    quickProgress,
    90,
  );
  quickProgressTimer = setInterval(() => void pollProgress(), 700);
  try {
    const textConfig = activeTextConfig.value;
    const quickDrama = quickDramaForm.value;
    const result = await request<{
      project: ProjectSummary & { chapters: Chapter[] };
      chapter: Chapter;
      production: Production;
    }>(quickCreatePath("drama"), {
      method: "POST",
      body: JSON.stringify({
        title: title || "一句话短剧",
        brief,
        genre: quickDrama.genre,
        style: quickDrama.style,
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
    quickDramaForm.value = defaultQuickDramaForm();
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

async function createJubenshaFromOneSentence(brief: string): Promise<void> {
  if (quickCreating.value || !(await ensureTextModelReady())) return;
  const title = quickIdea.value.title.trim();
  const quickJubensha = quickJubenshaForm.value;
  const playerCount = quickJubenshaForm.value.player_count;
  const duration = quickJubenshaForm.value.duration;
  quickCreating.value = true;
  const progressId = crypto.randomUUID();
  quickProgressTarget.value = 1;
  quickProgress.value = {
    status: "running",
    percent: 0,
    stage: "建立圆桌档案",
    message: "正在提交剧本杀创作任务",
    error: "",
  };
  const pollProgress = async (): Promise<void> => {
    try {
      const result = await request<{ progress: QuickProgress }>(
        quickProgressPath("jubensha", progressId),
      );
      quickProgressTarget.value = Math.max(
        quickProgressTarget.value,
        clampProgressPercent(result.progress.percent),
      );
      quickProgress.value = {
        ...result.progress,
        percent: quickProgress.value.percent,
      };
    } catch {
      // progress entry may not exist during the first round trip
    }
  };
  quickProgressAnimation = startProgressAnimation(
    quickProgress,
    60,
  );
  quickProgressTimer = setInterval(() => void pollProgress(), 700);
  try {
    const textConfig = activeTextConfig.value;
    const result = await request<{
      project: ProjectSummary & { chapters: Chapter[] };
      chapter: Chapter;
      jubensha_package: JubenshaPackage;
    }>(quickCreatePath("jubensha"), {
      method: "POST",
      body: JSON.stringify({
        title: title || "一句话开本",
        brief,
        genre: quickJubensha.genre,
        style: quickJubensha.style,
        player_count: playerCount,
        duration,
        progress_id: progressId,
        model_config: textConfig || undefined,
      }),
    });
    result.chapter.production = result.jubensha_package;
    currentProject.value = result.project;
    currentProjectDetail.value = result.project;
    currentChapter.value = result.chapter;
    setChapterDraft(result.chapter);
    route.value = "storyboard";
    quickProgressTarget.value = 100;
    quickProgress.value = {
      status: "completed",
      percent: quickProgress.value.percent,
      stage: "开本制作包已完成",
      message: "开本制作包、玩家本、角色线索和复盘已生成并保存",
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
    quickJubenshaForm.value = defaultQuickJubenshaForm();
    await loadProjects();
    await MessagePlugin.success("开本制作包已生成");
  } catch (error) {
    await pollProgress();
    quickProgress.value = {
      ...quickProgress.value,
      status: "failed",
      error: error instanceof Error ? error.message : "生成失败",
    };
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

async function createNovelFromOneSentence(brief: string): Promise<void> {
  if (quickCreating.value || !(await ensureTextModelReady())) return;
  const title = quickIdea.value.title.trim();
  const quickNovel = quickNovelForm.value;
  quickCreating.value = true;
  const progressId = crypto.randomUUID();
  quickProgressTarget.value = 1;
  quickProgress.value = {
    status: "running",
    percent: 0,
    stage: "建立作品",
    message: "正在提交网文创作任务",
    error: "",
  };
  const pollProgress = async (): Promise<void> => {
    try {
      const result = await request<{ progress: QuickProgress }>(
        quickProgressPath("novel", progressId),
      );
      quickProgressTarget.value = Math.max(
        quickProgressTarget.value,
        clampProgressPercent(result.progress.percent),
      );
      quickProgress.value = {
        ...result.progress,
        percent: quickProgress.value.percent,
      };
    } catch {
      // progress entry may not exist during the first round trip
    }
  };
  quickProgressAnimation = startProgressAnimation(
    quickProgress,
    60,
  );
  quickProgressTimer = setInterval(() => void pollProgress(), 700);
  try {
    const textConfig = activeTextConfig.value;
    const result = await request<{
      project: ProjectSummary & { chapters: Chapter[] };
      chapter: Chapter;
      novel_package: NovelPackage;
    }>(quickCreatePath("novel"), {
      method: "POST",
      body: JSON.stringify({
        title: title || "一句话网文",
        brief,
        genre: quickNovel.genre,
        style: quickNovel.style,
        progress_id: progressId,
        target_platform: "番茄小说",
        target_words: 2800,
        model_config: textConfig || undefined,
      }),
    });
    result.chapter.production = result.novel_package;
    currentProject.value = result.project;
    currentProjectDetail.value = result.project;
    currentChapter.value = result.chapter;
    setChapterDraft(result.chapter);
    route.value = "storyboard";
    quickProgressTarget.value = 100;
    quickProgress.value = {
      status: "completed",
      percent: quickProgress.value.percent,
      stage: "连载方案已完成",
      message: "连载方案、首章和发布检查已生成并保存",
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
    quickNovelForm.value = defaultQuickNovelForm();
    await loadProjects();
    await MessagePlugin.success("连载方案已生成");
  } catch (error) {
    await pollProgress();
    quickProgress.value = {
      ...quickProgress.value,
      status: "failed",
      error: error instanceof Error ? error.message : "生成失败",
    };
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
      resetChapterDraft();
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

function requestChapterDeletion(chapter: Chapter): void {
  chapterPendingDeletion.value = chapter;
  showDeleteChapter.value = true;
}

async function deleteChapter(): Promise<void> {
  const project = currentProject.value;
  const chapter = chapterPendingDeletion.value;
  if (!project || !chapter || deletingChapter.value) return;
  deletingChapter.value = true;
  try {
    await request(`/api/projects/${project.id}/chapters/${chapter.id}`, {
      method: "DELETE",
    });
    const remainingChapters =
      currentProjectDetail.value?.chapters.filter((item) => item.id !== chapter.id) || [];
    if (currentProjectDetail.value) {
      currentProjectDetail.value.chapters = remainingChapters;
    }
    if (currentChapter.value?.id === chapter.id) {
      const nextChapter =
        remainingChapters.find((item) => item.episode_no > chapter.episode_no) ||
        remainingChapters[remainingChapters.length - 1] ||
        null;
      currentChapter.value = nextChapter;
      chapterDraft.value = nextChapter
        ? {
            title: nextChapter.title,
            outline: nextChapter.outline,
            content: nextChapter.content,
          }
        : { title: "", outline: "", content: "" };
      activeShot.value = null;
    }
    chapterPendingDeletion.value = null;
    showDeleteChapter.value = false;
    await loadProjects();
    await MessagePlugin.success("章节及其全部资产已删除");
  } catch (error) {
    await showError(error);
  } finally {
    deletingChapter.value = false;
  }
}

function openCreateChapter(): void {
  newChapterEpisodeNo.value = nextEpisodeNo.value;
  newChapterForm.value = {
    title: `第 ${newChapterEpisodeNo.value} ${chapterUnitLabel.value}`,
    brief: "",
  };
  showCreateChapter.value = true;
}

async function createChapterRecord(): Promise<Chapter> {
  if (!currentProject.value) throw new Error("请先选择项目");
  const result = await request<{ chapter: Chapter }>(
    `/api/projects/${currentProject.value.id}/chapters`,
    {
      method: "POST",
      body: JSON.stringify({
        title:
          newChapterForm.value.title.trim() ||
          `第 ${newChapterEpisodeNo.value} ${chapterUnitLabel.value}`,
      }),
    },
  );
  if (currentProjectDetail.value)
    currentProjectDetail.value.chapters.push(result.chapter);
  selectChapter(result.chapter);
  return result.chapter;
}

async function createChapter(): Promise<void> {
  if (chapterCreating.value) return;
  chapterCreating.value = true;
  try {
    await createChapterRecord();
    showCreateChapter.value = false;
    await MessagePlugin.success(
      `第 ${currentChapter.value?.episode_no} ${chapterUnitLabel.value}已创建`,
    );
  } catch (error) {
    await showError(error);
  } finally {
    chapterCreating.value = false;
  }
}

async function draftNextChapter(): Promise<void> {
  const brief =
    newChapterForm.value.brief.trim() ||
    (isNovelMode.value
      ? "承接上一章状态，推进新的冲突、爽点和章节钩子。"
      : isJubenshaMode.value
        ? "承接上一幕已公开的信息，推进新的关系压力、证物投放或圆桌对质。"
        : "请完全参考上一集的剧情、结尾状态和未解决冲突，自动续写下一集，不要重复上一集内容。");
  if (chapterCreating.value || !(await ensureTextModelReady())) return;
  const project = currentProject.value;
  if (!project) return;
  chapterCreating.value = true;
  const progressId = crypto.randomUUID();
  chapterProgressTarget.value = 1;
  chapterProgress.value = {
    status: "running",
    percent: 0,
    stage: `创建下一${chapterUnitLabel.value}`,
    message: "正在创建新章节",
    error: "",
  };
  const pollProgress = async (): Promise<void> => {
    try {
      const result = await request<{ progress: QuickProgress }>(
        quickProgressPath(productMode.value, progressId),
      );
      chapterProgressTarget.value = Math.max(
        chapterProgressTarget.value,
        clampProgressPercent(result.progress.percent),
      );
      chapterProgress.value = {
        ...result.progress,
        percent: chapterProgress.value.percent,
      };
    } catch {
      // The progress entry may not exist while the chapter is being created.
    }
  };
  chapterProgressAnimation = startProgressAnimation(
    chapterProgress,
    isNovelMode.value || isJubenshaMode.value ? 60 : 90,
  );
  chapterProgressTimer = setInterval(() => void pollProgress(), 700);
  let createdChapter: Chapter | null = null;
  try {
    createdChapter = await createChapterRecord();
    chapterProgressTarget.value = Math.max(chapterProgressTarget.value, 20);
    chapterProgress.value = {
      ...chapterProgress.value,
      stage: `读取上一${chapterUnitLabel.value}`,
      message: `正在读取上一${chapterUnitLabel.value}剧情和结尾状态`,
    };
    const textConfig = activeTextConfig.value;
    const result = await request<{ chapter: Chapter; package_ready?: boolean }>(
      `/api/projects/${currentProject.value?.id}/chapters/${createdChapter.id}/draft`,
      {
        method: "POST",
        body: JSON.stringify({
          brief,
          progress_id: progressId,
          model_config: textConfig || undefined,
        }),
      },
    );
    let completedChapter = result.chapter;
    if (!result.package_ready) {
      if (chapterProgressTimer) clearInterval(chapterProgressTimer);
      chapterProgressTimer = null;
      chapterProgress.value = {
        ...chapterProgress.value,
        status: "running",
        stage: "生成制作包",
        message: `正在为本${chapterUnitLabel.value}生成对应制作包`,
      };
      const packageTextConfig = activeTextConfig.value;
      const aspectParts = project.aspect_ratio
        .split("/")
        .map((value) => value.trim());
      const packageBody = isNovelMode.value
        ? {
            source_text: completedChapter.content,
            brief: completedChapter.outline,
            target_platform: "番茄小说",
            target_words: 2800,
            model_config: packageTextConfig || undefined,
          }
        : isJubenshaMode.value
          ? {
              source_text: completedChapter.content,
              brief: completedChapter.outline,
              player_count: aspectParts[0] || "6人",
              duration: aspectParts[1] || "4小时",
              difficulty: "中等",
              model_config: packageTextConfig || undefined,
            }
          : {
              script: completedChapter.content,
              style: project.style,
              aspect_ratio: project.aspect_ratio,
              fps: 24,
              target_model: "model-agnostic",
              model_config: packageTextConfig || undefined,
            };
      const packageResult = await request<{ chapter: Chapter }>(
        chapterGeneratePath(
          productMode.value,
          project.id,
          completedChapter.id,
        ),
        { method: "POST", body: JSON.stringify(packageBody) },
      );
      completedChapter = packageResult.chapter;
    }
    currentChapter.value = completedChapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((chapter) =>
          chapter.id === completedChapter.id ? completedChapter : chapter,
        );
    setChapterDraft(completedChapter);
    chapterProgressTarget.value = 100;
    chapterProgress.value = {
      status: "completed",
      percent: chapterProgress.value.percent,
      stage: "制作包已完成",
      message: `第 ${completedChapter.episode_no} ${chapterUnitLabel.value}内容和制作包已保存`,
      error: "",
    };
    await new Promise<void>((resolve) => {
      const waitForProgress = window.setInterval(() => {
        if (chapterProgress.value.percent >= 100) {
          window.clearInterval(waitForProgress);
          resolve();
        }
      }, 40);
    });
    await new Promise((resolve) => setTimeout(resolve, 450));
    route.value = "storyboard";
    activeShot.value = shots.value[0] || null;
    showCreateChapter.value = false;
    await MessagePlugin.success(
      `第 ${completedChapter.episode_no} ${chapterUnitLabel.value}和制作包已完成`,
    );
  } catch (error) {
    await pollProgress();
    const message = createdChapter
      ? `第 ${createdChapter.episode_no} ${chapterUnitLabel.value}已创建，但 AI 续写或制作包生成失败：${
          error instanceof Error ? error.message : "操作失败"
        }`
      : error instanceof Error
        ? error.message
        : "AI 续写失败";
    chapterProgress.value = {
      ...chapterProgress.value,
      status: "failed",
      stage: "续写失败",
      message: "当前续写阶段未完成",
      error: message,
    };
    await showError(new Error(message));
  } finally {
    if (chapterProgressTimer) clearInterval(chapterProgressTimer);
    if (chapterProgressAnimation) clearInterval(chapterProgressAnimation);
    chapterProgressTimer = null;
    chapterProgressAnimation = null;
    chapterCreating.value = false;
    if (!showCreateChapter.value) {
      chapterProgress.value = {
        status: "idle",
        percent: 0,
        stage: "等待续写",
        message: "提交后将显示续写阶段",
        error: "",
      };
      chapterProgressTarget.value = 0;
    }
  }
}

watch(showCreateChapter, (visible) => {
  if (!visible && !chapterCreating.value) {
    chapterProgress.value = {
      status: "idle",
      percent: 0,
      stage: "等待续写",
      message: "提交后将显示续写阶段",
      error: "",
    };
    chapterProgressTarget.value = 0;
  }
});

watch(showPackageProgress, (visible) => {
  if (!visible) resetPackageProgress();
});

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
  const options =
    field === "genre"
      ? genreOptionsByProduct.value[productMode.value]
      : visualStyleOptionsByProduct.value[productMode.value];
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

function editableValue(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) {
    return value
      .map((item) => (isPlainObject(item) ? toReadableText(item, "") : String(item)))
      .filter(Boolean)
      .join("\n");
  }
  if (isPlainObject(value)) return toReadableText(value, "");
  return String(value);
}

function editableLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function packageField(
  key: string,
  label: string,
  value: unknown,
  options: Pick<PackageEditField, "multiline" | "lines"> = {},
): PackageEditField {
  return {
    key,
    label,
    value: editableValue(value),
    ...options,
  };
}

function openNovelCardEditor(card: DetailCard): void {
  const packageData = novelPackage.value;
  if (!packageData || !card.editTarget) return;
  const readerContract = isPlainObject(packageData.reader_contract)
    ? packageData.reader_contract
    : {};
  const topicReport = isPlainObject(packageData.topic_report)
    ? packageData.topic_report
    : {};
  const readerKey = Object.keys(readerContract).length ? "reader_contract" : "topic_report";
  const reader = readerKey === "reader_contract" ? readerContract : topicReport;
  const world = isPlainObject(packageData.world) ? packageData.world : {};

  if (card.editTarget === "novel-theme-main") {
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      title: card.title,
      fields: [
        packageField("title", "书名", packageData.title || currentProject.value?.title),
        packageField("genre", "题材", currentProject.value?.genre),
        packageField("positioning", "卖点", packageData.positioning, { multiline: true }),
      ],
    };
  } else if (card.editTarget === "novel-theme-reader") {
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      sourceKey: readerKey,
      title: card.title,
      fields: [
        packageField("target_reader", "目标读者", reader.target_reader, { multiline: true }),
        packageField("promise", "核心期待", reader.promise, { multiline: true }),
        packageField("commercial_hook", "开篇看点", reader.commercial_hook, { multiline: true }),
        packageField("risk_notes", "风险提示", reader.risk_notes, {
          multiline: true,
          lines: true,
        }),
      ],
    };
  } else if (card.editTarget === "novel-theme-world") {
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      title: card.title,
      fields: [
        packageField("background", "背景", world.background, { multiline: true }),
        packageField("power_system", "体系", world.power_system, { multiline: true }),
        packageField("rules", "规则", world.rules, {
          multiline: true,
          lines: true,
        }),
      ],
    };
  } else if (card.editTarget === "novel-character" && card.editIndex !== undefined) {
    const item = isPlainObject(packageData.characters[card.editIndex])
      ? packageData.characters[card.editIndex]
      : {};
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      index: card.editIndex,
      listKey: "characters",
      title: card.title,
      fields: [
        packageField("name", "角色名", item.name),
        packageField("role", "角色定位", item.role, { multiline: true }),
        packageField("goal", "当前目标", item.goal, { multiline: true }),
        packageField("arc", "成长变化", item.arc, { multiline: true }),
        packageField("tags", "标签", item.tags, { multiline: true, lines: true }),
      ],
    };
  } else if (card.editTarget === "novel-scene" && card.editIndex !== undefined) {
    const beats = Array.isArray((packageData.outline || {}).chapter_beats)
      ? (packageData.outline || {}).chapter_beats
      : [];
    const item = isPlainObject(beats[card.editIndex]) ? beats[card.editIndex] : {};
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      index: card.editIndex,
      listKey: "outline.chapter_beats",
      title: card.title,
      fields: [
        packageField("chapter", "所在章节", item.chapter),
        packageField("title", "节点标题", item.title || item.name),
        packageField("hook", "情节钩子", item.hook, { multiline: true }),
        packageField("payoff", "本章落点", item.payoff || item.goal, { multiline: true }),
      ],
    };
  } else if (card.editTarget === "novel-scene-chapter") {
    packageEditContext.value = {
      product: "novel",
      target: card.editTarget,
      title: card.title,
      fields: [
        packageField("chapter_title", "章节标题", packageData.chapter_title),
        packageField("chapter_outline", "章节方向", packageData.chapter_outline, {
          multiline: true,
        }),
        packageField("chapter_text", "章节正文", packageData.chapter_text, {
          multiline: true,
        }),
      ],
    };
  } else {
    return;
  }
  showPackageEditor.value = true;
}

function openJubenshaPlayerEditor(card: DetailCard): void {
  const packageData = jubenshaPackage.value;
  if (!packageData || card.editIndex === undefined || !card.editListKey) return;
  const packageRecord = packageData as Record<string, any>;
  const list = packageRecord[card.editListKey] || [];
  const item = isPlainObject(list[card.editIndex]) ? list[card.editIndex] : {};
  const fieldSource: Record<string, string> = {
    player_goal: item.player_goal ? "player_goal" : "motive",
    opening_scene: item.opening_scene ? "opening_scene" : "highlight_scene",
    script_text: item.script_text
      ? "script_text"
      : item.player_script
        ? "player_script"
        : "script",
  };
  packageEditContext.value = {
    product: "jubensha",
    target: "jubensha-player",
    index: card.editIndex,
    listKey: card.editListKey,
    fieldSource,
    title: card.title,
    fields: [
      packageField("seat", "席位", item.seat),
      packageField("name", "角色名", item.name),
      packageField("public_identity", "公开身份", item.public_identity, { multiline: true }),
      packageField("player_goal", "玩家目标", item[fieldSource.player_goal], { multiline: true }),
      packageField("private_secret", "隐藏秘密", item.private_secret, { multiline: true }),
      packageField("relationship_hook", "关系钩子", item.relationship_hook, { multiline: true }),
      packageField("opening_scene", "开场场面", item[fieldSource.opening_scene], { multiline: true }),
      packageField("known_information", "已知信息", item.known_information, {
        multiline: true,
        lines: true,
      }),
      packageField("hidden_information", "隐藏信息", item.hidden_information, {
        multiline: true,
        lines: true,
      }),
      packageField("script_text", "玩家本正文", item[fieldSource.script_text], {
        multiline: true,
      }),
    ],
  };
  showPackageEditor.value = true;
}

function openJubenshaClueEditor(card: DetailCard): void {
  const packageData = jubenshaPackage.value;
  if (!packageData || card.editIndex === undefined) return;
  const item = isPlainObject(packageData.clues[card.editIndex])
    ? packageData.clues[card.editIndex]
    : {};
  packageEditContext.value = {
    product: "jubensha",
    target: "jubensha-clue",
    index: card.editIndex,
    listKey: "clues",
    title: card.title,
    fields: [
      packageField("id", "线索编号", item.id),
      packageField("round", "投放轮次", item.round),
      packageField("visible_to", "可见对象", item.visible_to),
      packageField("truth_target", "指向真相", item.truth_target, { multiline: true }),
      packageField("dm_note", "DM提示", item.dm_note, { multiline: true }),
    ],
  };
  showPackageEditor.value = true;
}

function openJubenshaRoundEditor(card: DetailCard): void {
  const packageData = jubenshaPackage.value;
  if (!packageData || card.editIndex === undefined) return;
  const item = isPlainObject(packageData.rounds[card.editIndex])
    ? packageData.rounds[card.editIndex]
    : {};
  packageEditContext.value = {
    product: "jubensha",
    target: "jubensha-round",
    index: card.editIndex,
    listKey: "rounds",
    title: card.title,
    fields: [
      packageField("name", "轮次名", item.name),
      packageField("objective", "本轮目标", item.objective, { multiline: true }),
      packageField("pressure", "新压力", item.pressure, { multiline: true }),
      packageField("clue_release", "投放线索", item.clue_release, {
        multiline: true,
        lines: true,
      }),
      packageField("dm_cue", "主持提示", item.dm_cue, { multiline: true }),
    ],
  };
  showPackageEditor.value = true;
}

function openJubenshaAssetCardEditor(card: DetailCard): void {
  if (card.editTarget === "jubensha-clue") {
    openJubenshaClueEditor(card);
    return;
  }
  if (card.editTarget === "jubensha-round") {
    openJubenshaRoundEditor(card);
    return;
  }
  openJubenshaPlayerEditor(card);
}

function closePackageEditor(): void {
  if (packageEditSaving.value) return;
  showPackageEditor.value = false;
  packageEditContext.value = null;
}

function packageFieldMap(context: PackageEditContext): Record<string, PackageEditField> {
  return Object.fromEntries(context.fields.map((field) => [field.key, field]));
}

function applyPackageField(
  target: Record<string, any>,
  fields: Record<string, PackageEditField>,
  key: string,
  sourceKey = key,
): void {
  const field = fields[key];
  if (!field) return;
  target[sourceKey] = field.lines ? editableLines(field.value) : field.value.trim();
}

function replaceCurrentChapter(chapter: Chapter): void {
  currentChapter.value = chapter;
  if (currentProjectDetail.value) {
    currentProjectDetail.value.chapters = currentProjectDetail.value.chapters.map((item) =>
      item.id === chapter.id ? chapter : item,
    );
  }
}

async function savePackageEditor(): Promise<void> {
  const context = packageEditContext.value;
  const project = currentProject.value;
  const chapter = currentChapter.value;
  if (packageEditSaving.value || !context || !project || !chapter) return;
  const currentProduction = chapter.production;
  if (!currentProduction || !("type" in currentProduction)) return;
  const production = JSON.parse(JSON.stringify(currentProduction)) as Record<string, any>;
  const fields = packageFieldMap(context);
  const projectPatch: Record<string, string> = {};

  if (context.product === "novel") {
    if (context.target === "novel-theme-main") {
      applyPackageField(production, fields, "positioning");
      applyPackageField(production, fields, "title");
      projectPatch.title = fields.title?.value.trim() || project.title;
      projectPatch.genre = fields.genre?.value.trim() || project.genre;
      production.title = projectPatch.title;
    } else if (context.target === "novel-theme-reader") {
      const readerKey = context.sourceKey || "reader_contract";
      const reader = isPlainObject(production[readerKey]) ? production[readerKey] : {};
      applyPackageField(reader, fields, "target_reader");
      applyPackageField(reader, fields, "promise");
      applyPackageField(reader, fields, "commercial_hook");
      applyPackageField(reader, fields, "risk_notes");
      production[readerKey] = reader;
    } else if (context.target === "novel-theme-world") {
      const world = isPlainObject(production.world) ? production.world : {};
      applyPackageField(world, fields, "background");
      applyPackageField(world, fields, "power_system");
      applyPackageField(world, fields, "rules");
      production.world = world;
    } else if (
      context.target === "novel-character" &&
      context.index !== undefined &&
      Array.isArray(production.characters)
    ) {
      const item = isPlainObject(production.characters[context.index])
        ? production.characters[context.index]
        : {};
      applyPackageField(item, fields, "name");
      applyPackageField(item, fields, "role");
      applyPackageField(item, fields, "goal");
      applyPackageField(item, fields, "arc");
      applyPackageField(item, fields, "tags");
      production.characters[context.index] = item;
    } else if (
      context.target === "novel-scene" &&
      context.index !== undefined &&
      Array.isArray(production.outline?.chapter_beats)
    ) {
      const item = isPlainObject(production.outline.chapter_beats[context.index])
        ? production.outline.chapter_beats[context.index]
        : {};
      applyPackageField(item, fields, "chapter");
      applyPackageField(item, fields, "title");
      applyPackageField(item, fields, "hook");
      applyPackageField(item, fields, "payoff");
      production.outline.chapter_beats[context.index] = item;
    } else if (context.target === "novel-scene-chapter") {
      applyPackageField(production, fields, "chapter_title");
      applyPackageField(production, fields, "chapter_outline");
      applyPackageField(production, fields, "chapter_text");
    }
  } else if (
    context.product === "jubensha" &&
    context.index !== undefined &&
    context.listKey &&
    Array.isArray(production[context.listKey])
  ) {
    const item = isPlainObject(production[context.listKey][context.index])
      ? production[context.listKey][context.index]
      : {};
    for (const field of context.fields) {
      const sourceKey = context.fieldSource?.[field.key] || field.key;
      item[sourceKey] = field.lines ? editableLines(field.value) : field.value.trim();
    }
    production[context.listKey][context.index] = item;
  }

  packageEditSaving.value = true;
  try {
    const result = await request<{ chapter: Chapter }>(
      `/api/projects/${project.id}/chapters/${chapter.id}/production`,
      { method: "PATCH", body: JSON.stringify({ production }) },
    );
    replaceCurrentChapter(result.chapter);
    if (Object.keys(projectPatch).length) {
      const projectResult = await request<{ project: ProjectSummary }>(
        `/api/projects/${project.id}`,
        { method: "PATCH", body: JSON.stringify(projectPatch) },
      );
      currentProject.value = projectResult.project;
      projects.value = projects.value.map((item) =>
        item.id === projectResult.project.id ? projectResult.project : item,
      );
    }
    closePackageEditor();
    await MessagePlugin.success("内容已保存");
  } catch (error) {
    await showError(error);
  } finally {
    packageEditSaving.value = false;
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
    activeShot.value = (result.chapter.production as Production | null)?.shots.find(
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
  if (isNovelMode.value) {
    await generateNovelPackage();
    return;
  }
  if (isJubenshaMode.value) {
    await generateJubenshaPackage();
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
  const progress = startPackageProgress("drama");
  try {
    await saveChapter();
    chapterProgressTarget.value = Math.max(chapterProgressTarget.value, 5);
    const result = await request<{ project: Production; chapter: Chapter }>(
      chapterGeneratePath(
        "drama",
        currentProject.value.id,
        currentChapter.value.id,
      ),
      {
        method: "POST",
        body: JSON.stringify({
          script: chapterDraft.value.content,
          style: currentProject.value.style,
          aspect_ratio: currentProject.value.aspect_ratio,
          fps: 24,
          target_model: "model-agnostic",
          progress_id: progress.progressId,
          model_config: textConfig || undefined,
        }),
      },
    );
    currentChapter.value = result.chapter;
    currentChapter.value.production = result.project;
    await completePackageProgress("制作包已完成", "实体、分镜和提示词已生成并保存");
    route.value = "storyboard";
    activeShot.value = shots.value[0] || null;
    await loadProjects();
    await MessagePlugin.success("实体与分镜已生成");
  } catch (error) {
    await progress.poll();
    chapterProgress.value = {
      ...chapterProgress.value,
      status: "failed",
      stage: chapterProgress.value.stage || "制作包生成失败",
      message: "当前制作包生成阶段未完成",
      error: error instanceof Error ? error.message : "制作包生成失败",
    };
    await showError(error);
  } finally {
    progress.stop();
    generating.value = false;
    if (!showPackageProgress.value) resetPackageProgress();
  }
}

async function generateNovelPackage(): Promise<void> {
  if (!currentProject.value || !currentChapter.value) return;
  if (!(await ensureTextModelReady())) return;
  generating.value = true;
  const progress = startPackageProgress("novel");
  try {
    await saveChapter();
    chapterProgressTarget.value = Math.max(chapterProgressTarget.value, 5);
    const textConfig = activeTextConfig.value;
    const result = await request<{
      chapter: Chapter;
      novel_package: NovelPackage;
    }>(
      chapterGeneratePath(
        "novel",
        currentProject.value.id,
        currentChapter.value.id,
      ),
      {
        method: "POST",
        body: JSON.stringify({
          source_text: chapterDraft.value.content,
          brief: chapterDraft.value.outline,
          target_platform: "番茄小说",
          target_words: 2800,
          progress_id: progress.progressId,
          model_config: textConfig || undefined,
        }),
      },
    );
    result.chapter.production = result.novel_package;
    currentChapter.value = result.chapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((item) =>
          item.id === result.chapter.id ? result.chapter : item,
        );
    setChapterDraft(result.chapter);
    await completePackageProgress("连载方案已完成", "作品设定、章节正文和发布检查已生成并保存");
    route.value = "storyboard";
    await loadProjects();
    await MessagePlugin.success("连载方案已生成");
  } catch (error) {
    await progress.poll();
    chapterProgress.value = {
      ...chapterProgress.value,
      status: "failed",
      stage: chapterProgress.value.stage || "连载方案生成失败",
      message: "当前制作包生成阶段未完成",
      error: error instanceof Error ? error.message : "连载方案生成失败",
    };
    await showError(error);
  } finally {
    progress.stop();
    generating.value = false;
    if (!showPackageProgress.value) resetPackageProgress();
  }
}

async function generateJubenshaPackage(): Promise<void> {
  if (!currentProject.value || !currentChapter.value) return;
  if (!(await ensureTextModelReady())) return;
  generating.value = true;
  const progress = startPackageProgress("jubensha");
  try {
    await saveChapter();
    chapterProgressTarget.value = Math.max(chapterProgressTarget.value, 5);
    const textConfig = activeTextConfig.value;
    const [playerCount = "6人", duration = "4小时"] =
      currentProject.value.aspect_ratio
        .split("/")
        .map((value) => value.trim());
    const result = await request<{
      chapter: Chapter;
      jubensha_package: JubenshaPackage;
    }>(
      chapterGeneratePath(
        "jubensha",
        currentProject.value.id,
        currentChapter.value.id,
      ),
      {
        method: "POST",
        body: JSON.stringify({
          source_text: chapterDraft.value.content,
          brief: chapterDraft.value.outline,
          player_count: playerCount,
          duration,
          difficulty: "中等",
          progress_id: progress.progressId,
          model_config: textConfig || undefined,
        }),
      },
    );
    result.chapter.production = result.jubensha_package;
    currentChapter.value = result.chapter;
    if (currentProjectDetail.value)
      currentProjectDetail.value.chapters =
        currentProjectDetail.value.chapters.map((item) =>
          item.id === result.chapter.id ? result.chapter : item,
        );
    setChapterDraft(result.chapter);
    await completePackageProgress("开本制作包已完成", "玩家本、线索、轮次和复盘已生成并保存");
    route.value = "storyboard";
    await loadProjects();
    await MessagePlugin.success("开本制作包已生成");
  } catch (error) {
    await progress.poll();
    chapterProgress.value = {
      ...chapterProgress.value,
      status: "failed",
      stage: chapterProgress.value.stage || "开本制作包生成失败",
      message: "当前制作包生成阶段未完成",
      error: error instanceof Error ? error.message : "开本制作包生成失败",
    };
    await showError(error);
  } finally {
    progress.stop();
    generating.value = false;
    if (!showPackageProgress.value) resetPackageProgress();
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
  resetChapterDraft();
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
    const packageLabel = "资源包";
    link.download = `${currentProject.value?.title || "项目"}-${currentChapter.value?.title || "章节"}-${packageLabel}.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    await MessagePlugin.success(exportLauncherSuccessLabel.value);
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
      confirmed: "已定稿",
      待确认: "可编辑",
    }[value] || value
  );
}

type DetailRow = { label: string; value: string };
type DetailCard = {
  key: string;
  eyebrow: string;
  title: string;
  rows: DetailRow[];
  chips?: string[];
  wide?: boolean;
  scriptText?: string;
  editTarget?: string;
  editIndex?: number;
  editListKey?: "characters" | "outline.chapter_beats" | "player_books" | "roles" | "clues" | "rounds";
};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toReadableText(value: unknown, fallback = "待确认"): string {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") {
    const text = value.trim();
    return text || fallback;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const items = value.map((item) => toReadableText(item, "")).filter(Boolean);
    return items.length ? items.join(" · ") : fallback;
  }
  if (isPlainObject(value)) {
    const preferredKeys = [
      "name",
      "title",
      "label",
      "text",
      "summary",
      "description",
      "value",
      "objective",
      "goal",
      "hook",
      "promise",
      "background",
      "ending",
      "content",
      "mainline",
      "opening_question",
      "player_count",
      "duration",
      "genre_blend",
      "difficulty",
      "main_hook",
      "dm_load",
    ];
    for (const key of preferredKeys) {
      const text = toReadableText(value[key], "");
      if (text) return text;
    }
  }
  return fallback;
}

function toChipList(value: unknown, limit = 4): string[] {
  if (!Array.isArray(value)) {
    const text = toReadableText(value, "");
    return text ? [text] : [];
  }
  return value
    .map((item) => toReadableText(item, ""))
    .filter(Boolean)
    .slice(0, limit);
}

function summarizeObjectList(
  value: unknown,
  keys: string[],
  limit = 3,
): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .slice(0, limit)
    .map((item) => {
      if (isPlainObject(item)) {
        const parts = keys.map((key) => toReadableText(item[key], "")).filter(Boolean);
        if (parts.length) return parts.join(" · ");
      }
      return toReadableText(item, "");
    })
    .filter(Boolean);
}

function detailRow(label: string, value: unknown): DetailRow {
  return { label, value: toReadableText(value) };
}

const novelOverviewCards = computed<DetailCard[]>(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  const reader = packageData.reader_contract || packageData.topic_report || {};
  const radar = packageData.opening_radar || {};
  const world = packageData.world || {};
  const outline = packageData.outline || {};
  const serial = packageData.serial_plan || {};
  const quality = packageData.quality_gate || packageData.review_report || {};
  const publish = packageData.publish_gate || packageData.finalize || {};
  const characters = summarizeObjectList(packageData.characters, ["name", "role", "goal"], 4);
  return [
    {
      key: "novel-reader",
      eyebrow: "作品卖点",
      title: packageData.title || currentProject.value?.title || "作品定位",
      wide: true,
      rows: [
        detailRow("一句话卖点", packageData.positioning),
        detailRow("读者期待", reader.promise || reader.target_reader),
        detailRow("题材标签", [currentProject.value?.genre, currentProject.value?.style].filter(Boolean)),
      ],
      chips: toChipList(reader.commercial_hook || reader.risk_notes, 4),
    },
    {
      key: "novel-cast",
      eyebrow: "人物关系",
      title: "主角与核心关系",
      rows: [
        detailRow("主角定位", characters[0]),
        detailRow("关系张力", characters.slice(1, 3)),
        detailRow("成长方向", summarizeObjectList(packageData.characters, ["arc"], 3)),
      ],
      chips: characters,
    },
    {
      key: "novel-world",
      eyebrow: "世界场景",
      title: "世界规则",
      rows: [
        detailRow("背景", world.background),
        detailRow("体系", world.power_system),
        detailRow("规则", summarizeObjectList(world.rules, ["name", "title", "text"], 3)),
      ],
      chips: toChipList(world.rules, 4),
    },
    {
      key: "novel-outline",
      eyebrow: "分卷主线",
      title: "主线与分卷",
      rows: [
        detailRow("主线", outline.mainline),
        detailRow("分卷目标", summarizeObjectList(outline.volumes, ["title", "goal"], 4)),
        detailRow("章节节点", summarizeObjectList(outline.chapter_beats, ["chapter", "title"], 4)),
      ],
      chips: toChipList(outline.chapter_beats, 4),
    },
    {
      key: "novel-radar",
      eyebrow: "章节钩子",
      title: "前三章追读",
      rows: [
        detailRow("第一章", radar.chapter_1_hook),
        detailRow("第二章", radar.chapter_2_push),
        detailRow("第三章", radar.chapter_3_payoff),
      ],
      chips: toChipList(radar.retention_risks, 4),
    },
    {
      key: "novel-quality",
      eyebrow: "追更发布",
      title: "更新与发布检查",
      wide: true,
      rows: [
        detailRow("更新节奏", serial.update_unit),
        detailRow("存稿窗口", summarizeObjectList(serial.runway, ["title", "goal"], 3)),
        detailRow("发布格式", publish.platform_format),
        detailRow("修订项", quality.fixes || quality.logic_issues || quality.language_issues),
      ],
      chips: [
        ...toChipList(serial.feedback_metrics, 4),
        ...toChipList(packageData.style_pass, 3),
      ],
    },
  ];
});

const novelOutlineTabs = computed(() => [
  { key: "chapter", title: "本章追读", meta: `${novelPackage.value?.word_count || chapterDraft.value.content.length} 字` },
  { key: "book", title: "作品骨架", meta: "卖点 / 主线" },
  { key: "cast", title: "人物关系", meta: `${novelPackage.value?.characters.length || 0} 人` },
  { key: "world", title: "世界场景", meta: "规则 / 节点" },
  { key: "release", title: "更新发布", meta: "节奏 / 质检" },
]);

const activeNovelOutlineCards = computed<DetailCard[]>(() => {
  const groups: Record<string, string[]> = {
    chapter: ["novel-radar"],
    book: ["novel-reader", "novel-outline"],
    cast: ["novel-cast"],
    world: ["novel-world"],
    release: ["novel-quality"],
  };
  const cardMap = new Map(novelOverviewCards.value.map((card) => [card.key, card]));
  return (groups[activeNovelOutlineTab.value] || groups.chapter)
    .map((key) => cardMap.get(key))
    .filter((card): card is DetailCard => Boolean(card));
});

const novelCharacterCards = computed<DetailCard[]>(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  return packageData.characters.map((character, index) => {
    const item = isPlainObject(character) ? character : {};
    return {
      key: String(item.name || item.role || index),
      eyebrow: `人物 ${String(index + 1).padStart(2, "0")}`,
      title: toReadableText(item.name, `角色 ${index + 1}`),
      editTarget: "novel-character",
      editIndex: index,
      editListKey: "characters",
      rows: [
        detailRow("角色定位", item.role),
        detailRow("当前目标", item.goal),
        detailRow("成长变化", item.arc),
      ],
      chips: toChipList(item.tags, 4),
    };
  });
});

const novelThemeCards = computed<DetailCard[]>(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  const world = packageData.world || {};
  const reader = packageData.reader_contract || packageData.topic_report || {};
  return [
    {
      key: "novel-theme-main",
      eyebrow: "作品定位",
      title: packageData.title || currentProject.value?.title || "书名与卖点",
      editTarget: "novel-theme-main",
      rows: [
        detailRow("书名", packageData.title || currentProject.value?.title),
        detailRow("题材", currentProject.value?.genre),
        detailRow("卖点", packageData.positioning),
      ],
      chips: toChipList(currentProject.value?.style, 4),
    },
    {
      key: "novel-theme-reader",
      eyebrow: "读者预期",
      title: "读者与爽点",
      editTarget: "novel-theme-reader",
      rows: [
        detailRow("目标读者", reader.target_reader),
        detailRow("核心期待", reader.promise),
        detailRow("开篇看点", reader.commercial_hook),
      ],
      chips: toChipList(reader.risk_notes, 4),
    },
    {
      key: "novel-theme-world",
      eyebrow: "世界规则",
      title: "世界与体系",
      editTarget: "novel-theme-world",
      rows: [
        detailRow("背景", world.background),
        detailRow("体系", world.power_system),
        detailRow("规则", toChipList(world.rules, 5)),
      ],
    },
  ];
});

const novelSceneCards = computed<DetailCard[]>(() => {
  const packageData = novelPackage.value;
  if (!packageData) return [];
  const outline = packageData.outline || {};
  const beats = Array.isArray(outline.chapter_beats) ? outline.chapter_beats : [];
  const scenes = beats.length
    ? beats
    : [
        {
          title: packageData.chapter_title,
          hook: packageData.chapter_outline,
          payoff: packageData.positioning,
        },
      ];
  return scenes.map((scene, index) => {
    const item = isPlainObject(scene) ? scene : {};
    return {
      key: String(item.title || item.chapter || index),
      eyebrow: `节点 ${String(index + 1).padStart(2, "0")}`,
      title: toReadableText(item.title || item.name, `章节节点 ${index + 1}`),
      editTarget: beats.length ? "novel-scene" : "novel-scene-chapter",
      editIndex: beats.length ? index : undefined,
      editListKey: beats.length ? "outline.chapter_beats" : undefined,
      rows: [
        detailRow("所在章节", item.chapter),
        detailRow("情节钩子", item.hook),
        detailRow("本章落点", item.payoff || item.goal),
      ],
    };
  });
});

const novelAssetCards = computed<DetailCard[]>(() => {
  if (novelAssetTab.value === "characters") return novelCharacterCards.value;
  if (novelAssetTab.value === "scenes") return novelSceneCards.value;
  return novelThemeCards.value;
});

function novelAssetCount(tab: "theme" | "characters" | "scenes"): number {
  if (tab === "characters") return novelCharacterCards.value.length;
  if (tab === "scenes") return novelSceneCards.value.length;
  return novelThemeCards.value.length;
}

const jubenshaOverviewCards = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  const contract = packageData.play_contract || packageData.table_contract || {};
  const truth = packageData.truth_spine || {};
  return [
    {
      key: "jubensha-contract",
      eyebrow: "开本定位",
      title: "开本定位",
      wide: true,
      rows: [
        detailRow("人数", contract.player_count),
        detailRow("时长", contract.duration),
        detailRow("类型组合", contract.genre_blend),
        detailRow("难度", contract.difficulty),
      ],
      chips: [toReadableText(contract.main_hook), toReadableText(contract.dm_load)].filter(Boolean),
    },
    {
      key: "jubensha-truth",
      eyebrow: "真相骨架",
      title: "真相骨架",
      wide: true,
      rows: [
        detailRow("开局疑问", truth.opening_question),
        detailRow("真相落点", truth.ending),
      ],
      chips: [
        ...summarizeObjectList(truth.truth_chain, ["name", "title", "text"], 3),
        ...summarizeObjectList(truth.timeline, ["name", "title", "text"], 3),
        ...summarizeObjectList(truth.twists, ["name", "title", "text"], 3),
      ],
    },
  ];
});

const jubenshaPlayerCards = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  const booksKey =
    Array.isArray(packageData.player_books) && packageData.player_books.length
      ? "player_books"
      : "roles";
  const books = packageData[booksKey] || [];
  return books.map((book, index) => {
      const item = isPlainObject(book) ? book : {};
      const scriptSource =
        toReadableText(item.script_text || item.player_script || item.script || "", "");
      const beats = toChipList(item.script_beats, 6);
      const fallbackLines = [
        `开场：${toReadableText(item.opening_scene || item.highlight_scene)}`,
        `目标：${toReadableText(item.player_goal || item.motive)}`,
        `关系：${toReadableText(item.relationship_hook)}`,
        `已知：${toChipList(item.known_information, 4).join(" / ") || "待确认"}`,
        `隐藏：${toChipList(item.hidden_information, 4).join(" / ") || "待确认"}`,
        `高光：${toReadableText(item.highlight_scene)}`,
      ];
      return {
        key: String(item.name || index),
        eyebrow: `C${String(index + 1).padStart(3, "0")}`,
        title: toReadableText(item.name, `角色 ${index + 1}`),
        editTarget: "jubensha-player",
        editIndex: index,
        editListKey: booksKey,
        rows: [
        detailRow("身份", item.public_identity),
        detailRow("目标", item.player_goal || item.motive),
        detailRow("秘密", item.private_secret),
      ],
        chips: [
          ...toChipList(item.known_information, 4),
          ...toChipList(item.hidden_information, 4),
          ...toChipList(item.script_beats, 3),
        ],
        // Legacy packages may not have explicit player-book prose yet; synthesize a readable version.
        scriptText:
          scriptSource ||
          (beats.length
            ? beats.map((beat, beatIndex) => `${beatIndex + 1}. ${beat}`).join("\n")
            : fallbackLines.join("\n")),
      };
    });
});

const jubenshaFullScriptText = computed(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return "待确认";
  if (packageData.full_script?.trim()) return packageData.full_script.trim();
  const contract = packageData.play_contract || packageData.table_contract || {};
  const truth = packageData.truth_spine || {};
  const dm = packageData.dm_manual || {};
  const gate = packageData.playability_gate || {};
  const clues = Array.isArray(packageData.clues) ? packageData.clues : [];
  const rounds = Array.isArray(packageData.rounds) ? packageData.rounds : [];
  const players = jubenshaPlayerCards.value;
  const lines = [
    `# ${toReadableText(packageData.title, currentProject.value?.title || "剧本杀")}`,
    "",
    `- 开本定位：${toReadableText(packageData.positioning)}`,
    `- 人数：${toReadableText(contract.player_count)}`,
    `- 时长：${toReadableText(contract.duration)}`,
    `- 类型组合：${toReadableText(contract.genre_blend)}`,
    `- 难度：${toReadableText(contract.difficulty)}`,
    "",
    "## 开局钩子",
    toReadableText(truth.opening_question || contract.main_hook),
    "",
    "## 故事骨架",
    ...toChipList(truth.truth_chain, 8).map((item) => `- ${item}`),
    "",
    "## 时间线",
    ...toChipList(truth.timeline, 8).map((item) => `- ${item}`),
    "",
    "## 反转",
    ...toChipList(truth.twists, 8).map((item) => `- ${item}`),
    "",
    "## 玩家本",
  ];
  players.forEach((player, index) => {
    lines.push(
      "",
      `### ${player.eyebrow} · ${player.title}`,
      `- 公开身份：${player.rows[0]?.value || "待确认"}`,
      `- 玩家目标：${player.rows[1]?.value || "待确认"}`,
      `- 隐藏秘密：${player.rows[2]?.value || "待确认"}`,
      `- 关系钩子：${player.rows[3]?.value || "待确认"}`,
      `- 开场场面：${player.rows[4]?.value || "待确认"}`,
      "",
      player.scriptText || `第 ${index + 1} 位玩家正文待确认`,
    );
  });
  lines.push(
    "",
    "## 线索表",
    ...clues.slice(0, 12).flatMap((clue, index) => {
      const item = isPlainObject(clue) ? clue : {};
      return [
        "",
        `### CLUE-${String(index + 1).padStart(3, "0")}`,
        `- 轮次：${toReadableText(item.round)}`,
        `- 可见对象：${toReadableText(item.visible_to)}`,
        `- 指向真相：${toReadableText(item.truth_target)}`,
        `- DM提示：${toReadableText(item.dm_note)}`,
      ];
    }),
    "",
    "## 轮次表",
    ...rounds.slice(0, 12).flatMap((round, index) => {
      const item = isPlainObject(round) ? round : {};
      return [
        "",
        `### 第 ${index + 1} 轮 · ${toReadableText(item.name)}`,
        `- 目标：${toReadableText(item.objective)}`,
        `- 压力：${toReadableText(item.pressure)}`,
        `- DM提示：${toReadableText(item.dm_cue)}`,
        `- 线索投放：${toChipList(item.clue_release, 6).join(" / ") || "待确认"}`,
      ];
    }),
    "",
    "## DM手册",
    `- 开场：${toReadableText(dm.opening)}`,
    `- 节奏：${toChipList(dm.pacing, 6).join(" / ") || "待确认"}`,
    `- 复盘顺序：${toChipList(dm.reveal_order, 6).join(" / ") || "待确认"}`,
    `- 安全边界：${toChipList(dm.safety_boundaries, 6).join(" / ") || "待确认"}`,
    "",
    "## 可玩性质检",
    `- 角色均衡：${toReadableText(gate.role_balance)}`,
    `- 证据路径：${toChipList(gate.evidence_paths, 6).join(" / ") || "待确认"}`,
    `- 卡死风险：${toChipList(gate.deadlock_risks, 6).join(" / ") || "待确认"}`,
    `- 修复动作：${toChipList(gate.fixes, 6).join(" / ") || "待确认"}`,
  );
  return lines.join("\n").trim();
});

const jubenshaClueCards = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  return packageData.clues.map((clue, index) => {
    const item = isPlainObject(clue) ? clue : {};
    return {
      key: String(item.id || index),
      eyebrow: `线索 ${String(index + 1).padStart(3, "0")}`,
      title: toReadableText(item.id, `线索 ${String(index + 1).padStart(3, "0")}`),
      editTarget: "jubensha-clue",
      editIndex: index,
      editListKey: "clues",
      rows: [
        detailRow("轮次", item.round),
        detailRow("可见对象", item.visible_to),
        detailRow("指向真相", item.truth_target),
        detailRow("DM提示", item.dm_note),
      ],
      chips: item.is_misdirect ? ["误导线索"] : [],
    };
  });
});

const jubenshaRoundCards = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  return packageData.rounds.map((round, index) => {
    const item = isPlainObject(round) ? round : {};
    return {
      key: String(item.name || index),
      eyebrow: `轮次 ${String(index + 1).padStart(2, "0")}`,
      title: toReadableText(item.name, `轮次 ${index + 1}`),
      editTarget: "jubensha-round",
      editIndex: index,
      editListKey: "rounds",
      rows: [
        detailRow("目标", item.objective),
        detailRow("压力", item.pressure),
        detailRow("DM提示", item.dm_cue),
      ],
      chips: toChipList(item.clue_release, 4),
    };
  });
});

const jubenshaAssetCards = computed<DetailCard[]>(() => {
  if (jubenshaAssetTab.value === "clues") return jubenshaClueCards.value;
  if (jubenshaAssetTab.value === "rounds") return jubenshaRoundCards.value;
  return jubenshaPlayerCards.value;
});

function jubenshaAssetCount(tab: "players" | "clues" | "rounds"): number {
  if (tab === "clues") return jubenshaClueCards.value.length;
  if (tab === "rounds") return jubenshaRoundCards.value.length;
  return jubenshaPlayerCards.value.length;
}

function jubenshaStageLabel(index: number, fallback: string): string {
  return toReadableText(jubenshaPackage.value?.stages?.[index], fallback);
}

const jubenshaReviewSections = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  const contract = packageData.play_contract || packageData.table_contract || {};
  const truth = packageData.truth_spine || {};
  const dm = packageData.dm_manual || {};
  const gate = packageData.playability_gate || {};
  return [
    {
      key: "contract",
      eyebrow: "01",
      title: jubenshaStageLabel(0, "席位契约"),
      rows: [
        detailRow("人数", contract.player_count),
        detailRow("时长", contract.duration),
        detailRow("类型", contract.genre_blend),
        detailRow("难度", contract.difficulty),
        detailRow("开局钩子", contract.main_hook || truth.opening_question),
      ],
    },
    {
      key: "hidden-lines",
      eyebrow: "02",
      title: jubenshaStageLabel(1, "暗线编排"),
      rows: [
        detailRow("角色暗线", summarizeObjectList(packageData.roles, ["name", "secret", "hidden_secret"], 6)),
        detailRow("玩家目标", summarizeObjectList(packageData.player_books || packageData.roles, ["goal", "player_goal", "objective"], 6)),
        detailRow("关系钩子", summarizeObjectList(packageData.player_books || packageData.roles, ["relationship_hook", "relationships"], 6)),
      ],
    },
    {
      key: "truth",
      eyebrow: "03",
      title: jubenshaStageLabel(2, "真相骨架"),
      rows: [
        detailRow("核心真相", truth.core_truth || truth.truth),
        detailRow("时间线", summarizeObjectList(truth.timeline, ["time", "event", "text"], 8)),
        detailRow("真相链", summarizeObjectList(truth.truth_chain, ["name", "title", "text"], 8)),
        detailRow("反转", summarizeObjectList(truth.twists, ["name", "title", "text"], 5)),
      ],
    },
    {
      key: "clues",
      eyebrow: "04",
      title: jubenshaStageLabel(3, "证物投放"),
      rows: [
        detailRow("关键证物", summarizeObjectList(packageData.clues, ["name", "truth_target", "dm_note"], 8)),
        detailRow("道具清单", summarizeObjectList(packageData.props, ["name", "use", "appearance"], 8)),
      ],
    },
    {
      key: "rounds",
      eyebrow: "05",
      title: jubenshaStageLabel(4, "轮次压强"),
      rows: [
        detailRow("轮次目标", summarizeObjectList(packageData.rounds, ["name", "objective"], 8)),
        detailRow("线索释放", summarizeObjectList(packageData.rounds, ["clue_release"], 8)),
        detailRow("压力控制", summarizeObjectList(packageData.rounds, ["pressure"], 8)),
      ],
    },
    {
      key: "dm",
      eyebrow: "06",
      title: jubenshaStageLabel(5, "DM控场"),
      rows: [
        detailRow("开场", dm.opening),
        detailRow("控场节奏", summarizeObjectList(dm.pacing, ["name", "title", "text"], 6)),
        detailRow("复盘顺序", summarizeObjectList(dm.reveal_order, ["name", "title", "text"], 6)),
      ],
      chips: toChipList(dm.safety_boundaries, 4),
    },
    {
      key: "gate",
      eyebrow: "07",
      title: jubenshaStageLabel(6, "复盘闸门"),
      rows: [
        detailRow("角色平衡", gate.role_balance),
        detailRow("证据路径", summarizeObjectList(gate.evidence_paths, ["name", "title", "text"], 5)),
        detailRow("卡死风险", gate.deadlock_risks),
        detailRow("修复动作", gate.fixes),
      ],
    },
    {
      key: "full-script",
      eyebrow: "整本剧本",
      title: packageData.chapter_title,
      rows: [],
      wide: true,
      scriptText: jubenshaFullScriptText.value,
    },
  ];
});

const jubenshaReviewTabs = computed(() => [
  { key: "contract", title: "开本契约", meta: "席位 / 暗线" },
  { key: "truth", title: "真相证物", meta: `${jubenshaPackage.value?.clues.length || 0} 证物` },
  { key: "rounds", title: "轮次控场", meta: `${jubenshaPackage.value?.rounds.length || 0} 轮` },
  { key: "gate", title: "可玩性质检", meta: "复盘闸门" },
  { key: "script", title: "整本剧本", meta: "正文" },
]);

const activeJubenshaReviewCards = computed<DetailCard[]>(() => {
  const groups: Record<string, string[]> = {
    contract: ["contract", "hidden-lines"],
    truth: ["truth", "clues"],
    rounds: ["rounds", "dm"],
    gate: ["gate"],
    script: ["full-script"],
  };
  const cardMap = new Map(jubenshaReviewSections.value.map((card) => [card.key, card]));
  return (groups[activeJubenshaReviewTab.value] || groups.contract)
    .map((key) => cardMap.get(key))
    .filter((card): card is DetailCard => Boolean(card));
});

function jubenshaReviewSectionId(key: string): string {
  return `jubensha-review-${key}`;
}

async function scrollToJubenshaReview(key: string): Promise<void> {
  activeJubenshaReviewKey.value = key;
  await nextTick();
  document.getElementById(jubenshaReviewSectionId(key))?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

const jubenshaStoryboardCards = computed<DetailCard[]>(() => {
  const packageData = jubenshaPackage.value;
  if (!packageData) return [];
  const dm = packageData.dm_manual || {};
  const gate = packageData.playability_gate || {};
  return [
    {
      key: "jubensha-opening",
      eyebrow: "开场朗读",
      title: packageData.chapter_title,
      wide: true,
      rows: [
        detailRow("开场朗读", packageData.opening_script),
      ],
    },
    {
      key: "jubensha-dm",
      eyebrow: "DM复盘",
      title: "DM复盘",
      rows: [
        detailRow("开场", dm.opening),
        detailRow("节奏", summarizeObjectList(dm.pacing, ["name", "title", "text"], 3)),
        detailRow("复盘顺序", summarizeObjectList(dm.reveal_order, ["name", "title", "text"], 4)),
      ],
      chips: toChipList(dm.safety_boundaries, 4),
    },
    {
      key: "jubensha-props",
      eyebrow: "道具清单",
      title: "道具清单",
      rows: summarizeObjectList(
        packageData.props,
        ["name", "use", "appearance"],
        6,
      ).map((value, index) => ({ label: `道具 ${index + 1}`, value })),
    },
    {
      key: "jubensha-gate",
      eyebrow: "可玩性检查",
      title: "可玩性检查",
      wide: true,
      rows: [
        detailRow("角色平衡", gate.role_balance),
        detailRow("证据路径", summarizeObjectList(gate.evidence_paths, ["name", "title", "text"], 3)),
        detailRow("卡死风险", gate.deadlock_risks),
        detailRow("修复动作", gate.fixes),
      ],
    },
  ];
});

async function refreshRuntimeStatus(): Promise<void> {
  try {
    const runtime = await request<{
      version?: string;
      offline_demo: boolean;
      environment_model_configured: boolean;
      environment_model: string;
      cc_switch: CCSwitchRuntime;
    }>("/api/runtime");
    if (runtime.version) appVersion.value = runtime.version;
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
  if (chapterProgressTimer) clearInterval(chapterProgressTimer);
  if (chapterProgressAnimation) clearInterval(chapterProgressAnimation);
  document.removeEventListener("click", handleImportButtonClick);
  scriptFileInput.value?.remove();
  scriptFileInput.value = null;
});
</script>

<template>
  <div
    v-if="!user"
    class="auth-shell"
    :class="productClassMap()"
  >
    <section class="auth-art">
      <div class="brand-lockup">
        <span class="logo-dumpling" aria-hidden="true"></span
        ><span
          ><strong>{{ productName }}</strong><small>JIAOZI CREATOR SUITE</small></span
        >
      </div>
      <p class="eyebrow">JIAOZI CREATOR SUITE</p>
      <h1 v-if="isNovelMode">把一个脑洞，<br /><em>写成一本网文。</em></h1>
      <h1 v-else-if="isJubenshaMode" class="jubensha-auth-title">
        把一个秘密，<br /><em>围成一桌剧本杀。</em>
      </h1>
      <h1 v-else>把一个故事，<br /><em>做成一部短剧。</em></h1>
      <p class="auth-lede">
        {{
          isNovelMode
            ? "开篇钩子、人物关系、设定、章节节奏和连载发布，在同一张写作台上推进。"
            : isJubenshaMode
              ? "席位契约、暗线编排、真相骨架、证物投放和 DM 复盘，在同一张圆桌上闭环。"
              : "剧本、角色、场景、道具与逐镜提示词，在同一个创作流程里完成。"
        }}
      </p>
      <div class="auth-stamp">
        <span>{{ productSubtitle }}</span><span>{{ productIndex }} / 04</span>
      </div>
    </section>
    <section class="auth-panel">
      <div class="auth-panel-top">
        <span class="mini-brand">{{ productName }}</span><span>本地创作空间</span>
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
        <div class="product-login-switch">
          <button
            :class="{ active: productMode === 'drama' }"
            type="button"
            @click="setProductMode('drama')"
          >
            短剧
          </button>
          <button
            :class="{ active: productMode === 'novel' }"
            type="button"
            @click="setProductMode('novel')"
          >
            网文
          </button>
          <button
            :class="{ active: productMode === 'jubensha' }"
            type="button"
            @click="setProductMode('jubensha')"
          >
            剧本杀
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
              name="username"
              autocomplete="username"
              placeholder="你的创作者名称" /></t-form-item
          ><t-form-item v-if="authMode === 'register'" label="邮箱"
            ><t-input
              v-model="authForm.email"
              name="email"
              autocomplete="email"
              placeholder="可选" /></t-form-item
          ><t-form-item v-else label="账号"
            ><t-input
              v-model="authForm.identity"
              name="username"
              autocomplete="username"
              placeholder="用户名或邮箱" /></t-form-item
          ><t-form-item label="密码"
            ><t-input
              v-model="authForm.password"
              name="password"
              type="password"
              :autocomplete="authMode === 'register' ? 'new-password' : 'current-password'"
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
    :class="productClassMap()"
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
      v-if="exportLauncherVisible"
      class="prompt-export-launcher"
      type="button"
      :disabled="exportingPackage"
      @click="exportProductionPackage"
    >
      <FileImportIcon /><span>{{
        exportingPackage ? "正在导出" : exportLauncherLabel
      }}</span>
    </button>
    <aside class="studio-sidebar">
      <div class="side-brand">
        <span class="brand-knot" aria-hidden="true"></span>
        <div><strong>饺子创作台</strong><small>{{ productName }} · {{ productSubtitle }}</small></div>
      </div>
      <div class="product-suite-switch">
        <button
          :class="{ active: productMode === 'drama' }"
          type="button"
          @click="setProductMode('drama')"
        >
          短剧
        </button>
        <button
          :class="{ active: productMode === 'novel' }"
          type="button"
          @click="setProductMode('novel')"
        >
          网文
        </button>
        <button
          :class="{ active: productMode === 'jubensha' }"
          type="button"
          @click="setProductMode('jubensha')"
        >
          剧本杀
        </button>
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
        <p>{{ workflowLabel }}</p>
        <button
          :class="{ active: route === 'script' }"
          :disabled="!currentProject"
          @click="setRoute('script')"
        >
          <WriteIcon />{{ firstNavLabel }}</button
        ><button
          :class="{ active: route === 'assets' }"
          :disabled="isNovelMode ? !novelPackage : isJubenshaMode ? !jubenshaPackage : !dramaProduction"
          @click="setRoute('assets')"
        >
          <LayersIcon />{{ secondNavLabel }}</button
        ><button
          :class="{ active: route === 'storyboard' }"
          :disabled="!currentChapter"
          @click="setRoute('storyboard')"
        >
          <ViewListIcon />{{ thirdNavLabel }}
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
            <span class="eyebrow">PROJECT LIBRARY / {{ productIndex }}</span>
            <h1>{{ libraryTitle }}</h1>
            <p>
              {{ libraryDescription }}
            </p>
          </div>
          <div class="library-actions">
            <t-button
              class="quick-create-button"
              theme="primary"
              @click="showQuickCreate = true"
              ><WriteIcon />{{ quickCreateLabel }}</t-button
            >
            <t-button
              class="new-project-button"
              variant="outline"
              @click="showCreateProject = true"
              ><AddIcon />新建{{ productNoun }}</t-button
            >
          </div>
        </div>
        <div class="overview-ribbon">
          <div>
            <small>进行中的{{ productNoun }}</small><strong>{{ filteredProjects.length }}</strong>
          </div>
          <div>
            <small>{{ isNovelMode ? "已生成阶段" : isJubenshaMode ? "已投放线索" : "已提取镜头" }}</small
            ><strong>{{
              filteredProjects.reduce(
                (sum, item) => sum + projectGeneratedCount(item),
                0,
              )
            }}</strong>
          </div>
          <div>
            <small>{{ isNovelMode ? "完稿就绪度" : isJubenshaMode ? "开本就绪度" : "素材完成度" }}</small
            ><strong
              >{{
                filteredProjects.length
                  ? Math.round(
                      (filteredProjects.reduce(
                        (sum, item) =>
                          sum +
                          (projectIsPackaged(item) ? 1 : 0),
                        0,
                      ) /
                        filteredProjects.length) *
                        100,
                    )
                  : 0
              }}%</strong
            >
          </div>
          <div class="ribbon-note">
            <TimeIcon /><span
              >最近活动<br /><b>{{
                filteredProjects[0]?.latest_chapter_title ||
                (isNovelMode ? "从第一本书开始" : isJubenshaMode ? "从第一张圆桌开始" : "从第一个项目开始")
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
                ><span>{{
                  projectMetricText(project)
                }}</span
                ><span class="status-dot" :class="project.status"></span>
              </div>
            </div>
            <button
              class="tile-delete-button"
              type="button"
              :title="`删除${productNoun}`"
              @click.stop="requestProjectDeletion(project)"
            >
              <DeleteIcon />
            </button>
          </article>
          <button
            class="project-tile new-tile"
            @click="showCreateProject = true"
          >
            <AddIcon /><span>建立新{{ productNoun }}</span><small>从一个故事概念开始</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <FilmIcon />
          <h3>还没有{{ productNoun }}</h3>
          <p>{{ isNovelMode ? "新建一本书，把第一个脑洞放进连载线。" : isJubenshaMode ? "新建一个本，把第一个秘密放上圆桌。" : "新建一个项目，把第一个故事放上时间线。" }}</p>
          <t-button theme="primary" @click="showCreateProject = true"
            ><AddIcon />新建{{ productNoun }}</t-button
          >
        </div>
      </section>
      <section
        v-else-if="route === 'script'"
        class="page-area workspace-page"
        :class="{ 'novel-writing-page': isNovelMode, 'jubensha-writing-page': isJubenshaMode }"
      >
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >{{ isNovelMode ? "NOVEL DESK" : isJubenshaMode ? "JUBENSHA DESK" : "WRITING ROOM" }} / {{ currentProject?.genre }}</span
            >
            <h1>{{ isNovelMode ? "章节写作台" : isJubenshaMode ? "开本写作台" : currentProject?.title }}</h1>
            <p v-if="!isNovelMode && !isJubenshaMode">
              {{
                currentProject?.description ||
                "在这里把故事写成可以拍摄的章节。"
              }}
            </p>
            <div v-else class="workspace-meta">
              <span>{{ currentProject?.title }}</span>
              <span>{{ currentProject?.style }}</span>
              <span>{{ currentProjectDetail?.chapters.length || 0 }} {{ chapterUnitLabel }}</span>
            </div>
          </div>
          <div class="heading-actions">
            <t-button variant="outline" @click="openCreateChapter"
              ><AddIcon />续写下一{{ chapterUnitLabel }}</t-button
            ><t-button
              theme="primary"
              :loading="generating"
              @click="generateProduction"
              ><FilmIcon />{{ packageButtonLabel }}</t-button
            >
          </div>
        </div>
        <div class="work-layout">
          <aside class="chapter-rail">
            <div class="rail-title">
              <span>章节</span
              ><small
                >{{ currentProjectDetail?.chapters.length || 0 }} {{ chapterUnitLabel }}</small
              >
            </div>
            <div
              v-for="chapter in currentProjectDetail?.chapters"
              :key="chapter.id"
              class="chapter-item"
              role="button"
              tabindex="0"
              :class="{ active: chapter.id === currentChapter?.id }"
              @click="selectChapter(chapter)"
              @keydown.enter="selectChapter(chapter)"
              @keydown.space.prevent="selectChapter(chapter)"
            >
              <span class="chapter-no">{{
                String(chapter.episode_no).padStart(2, "0")
              }}</span
              ><span class="chapter-copy"
                ><strong>{{ chapter.title }}</strong
                ><small>{{ statusLabel(chapter.status) }}</small></span
              ><span class="chapter-item-actions"
                ><button
                  type="button"
                  class="chapter-status-delete-button"
                  :class="{ completed: chapter.status === 'completed' }"
                  title="删除章节"
                  :aria-label="`删除${chapter.title}`"
                  @click.stop="requestChapterDeletion(chapter)"
                  ><CheckCircleIcon
                    v-if="chapter.status === 'completed'"
                    class="chapter-complete-icon"
                  /><CloseIcon class="chapter-delete-icon" /></button></span
            ></div
            ><button class="rail-add" type="button" @click="openCreateChapter">
              <AddIcon />续写下一{{ chapterUnitLabel }}
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
                  >{{ isNovelMode ? "查看大纲" : isJubenshaMode ? "查看复盘" : "查看分镜" }}</t-button
                >
              </div>
            </div>
            <div class="editor-columns">
              <div>
                <label>{{ isNovelMode ? "本章方向" : isJubenshaMode ? "本幕方向" : "本章梗概" }}</label
                ><textarea
                  v-model="chapterDraft.outline"
                  class="outline-input"
                  :placeholder="
                    isNovelMode
                      ? '这一章要推进什么，最后卡在哪个点上？'
                      : isJubenshaMode
                        ? '这一幕要把谁逼到什么位置，最后留下什么疑点？'
                      : '这集必须发生什么？情绪从哪里开始，到哪里结束？'
                  "
                ></textarea
                ><label>{{ isNovelMode ? "章节正文" : isJubenshaMode ? "开本正文" : "剧本正文" }}</label
                ><textarea
                  v-model="chapterDraft.content"
                  class="script-input"
                  :placeholder="
                    isNovelMode
                      ? '第1章\n\n雨夜，主角推开便利店的门。\n\n他原本只想买一瓶水，却在货架背后看见了不该存在的名字。'
                      : isJubenshaMode
                        ? '第1幕\n\n闭馆钟声刚落，六位旧友在走廊里重逢。\n\n桌上多出一封写给死者的邀请函。'
                        : '场景：INT. 雨夜便利店 - 夜\n\n林默推门而入。玻璃门上的风铃轻响。\n\n林默（低声）：你果然在这里。'
                  "
                ></textarea>
              </div>
              <aside
                class="writing-guide"
                :class="{
                  'novel-writing-guide': isNovelMode,
                  'jubensha-writing-guide': isJubenshaMode,
                }"
              >
                <template v-if="isNovelMode">
                  <span class="guide-mark">✦</span>
                  <h3>本章卡片</h3>
                  <div class="novel-writing-stats">
                    <div v-for="item in novelWritingStats" :key="item.label" class="novel-writing-stat">
                      <span>{{ item.label }}</span><strong>{{ item.value }}</strong>
                    </div>
                  </div>
                  <div class="guide-line"></div>
                  <button class="import-button">
                    <FileImportIcon />导入章节
                  </button>
                </template>
                <template v-else-if="isJubenshaMode">
                  <span class="guide-mark">✦</span>
                  <h3>本幕卡片</h3>
                  <div class="novel-writing-stats">
                    <div
                      v-for="item in jubenshaWritingStats"
                      :key="item.label"
                      class="novel-writing-stat"
                    >
                      <span>{{ item.label }}</span><strong>{{ item.value }}</strong>
                    </div>
                  </div>
                  <div class="guide-line"></div>
                  <button class="import-button">
                    <FileImportIcon />导入幕本
                  </button>
                </template>
                <template v-else>
                  <span class="guide-mark">✦</span>
                  <h3>{{ isJubenshaMode ? "DM提示" : "导演提示" }}</h3>
                  <p>
                    {{
                      isJubenshaMode
                        ? "把开局疑问、角色关系、隐藏秘密和关键证物写清楚，系统会继续生成圆桌回环制作包。"
                        : "把“发生了什么”写清楚，智能体会继续推断镜头语言、角色状态和可执行的动作节奏。"
                    }}
                  </p>
                  <div class="guide-line"></div>
                  <small>支持 Word / PDF 导入<br />支持章节化持续创作</small
                  ><button class="import-button">
                    <FileImportIcon />导入剧本
                  </button>
                </template>
              </aside>
            </div>
          </div>
        </div>
      </section>
      <section
        v-else-if="route === 'assets' && isNovelMode"
        class="page-area workspace-page novel-package-page"
      >
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >作品设定 / {{ novelAssetCards.length }} 项</span
            >
            <h1>作品设定台</h1>
          </div>
        </div>
        <template v-if="novelPackage">
          <div class="asset-tabs">
            <button
              v-for="tab in [
                ['theme', '作品设定'],
                ['characters', '人物关系'],
                ['scenes', '世界场景'],
              ] as const"
              :key="tab[0]"
              :class="{ active: novelAssetTab === tab[0] }"
              type="button"
              @click="novelAssetTab = tab[0]"
            >
              {{ tab[1] }} <span>{{ novelAssetCount(tab[0]) }}</span>
            </button>
          </div>
          <div class="asset-grid">
            <article
              v-for="card in novelAssetCards"
              :key="card.key"
              class="asset-card package-edit-card"
              role="button"
              tabindex="0"
              @click="openNovelCardEditor(card)"
              @keydown.enter="openNovelCardEditor(card)"
            >
              <div class="asset-card-body">
                <div class="asset-card-content">
                  <div class="asset-card-topline">
                    <span class="asset-id">{{ card.eyebrow }}</span>
                    <button
                      type="button"
                      class="asset-action"
                      title="展开编辑"
                      aria-label="展开编辑"
                      @click.stop="openNovelCardEditor(card)"
                    >
                      <WriteIcon />
                    </button>
                  </div>
                  <h3>{{ card.title }}</h3>
                  <p v-for="row in card.rows" :key="row.label">
                    <b>{{ row.label }}</b>{{ row.value }}
                  </p>
                  <div v-if="card.chips?.length" class="detail-chip-list">
                    <span
                      v-for="chip in card.chips"
                      :key="chip"
                      class="detail-chip"
                      >{{ chip }}</span
                    >
                  </div>
                </div>
              </div>
            </article>
          </div>
        </template>
        <div v-else class="empty-state">
          <LayersIcon />
          <h3>还没有连载方案</h3>
          <p>先在正文页生成作品设定、首章正文和续写方向。</p>
        </div>
      </section>
      <section
        v-else-if="route === 'assets' && isJubenshaMode"
        class="page-area workspace-page jubensha-package-page"
      >
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >ASSET BIBLE / {{ jubenshaAssetCards.length }} CARDS</span
            >
            <h1>玩家本档案</h1>
          </div>
        </div>
        <template v-if="jubenshaPackage">
          <div class="asset-tabs">
            <button
              v-for="tab in [
                ['players', '玩家本'],
                ['clues', '证物'],
                ['rounds', '轮次'],
              ] as const"
              :key="tab[0]"
              :class="{ active: jubenshaAssetTab === tab[0] }"
              type="button"
              @click="jubenshaAssetTab = tab[0]"
            >
              {{ tab[1] }} <span>{{ jubenshaAssetCount(tab[0]) }}</span>
            </button>
          </div>
          <div class="asset-grid jubensha-asset-grid">
            <article
              v-for="card in jubenshaAssetCards"
              :key="card.key"
              class="asset-card package-edit-card jubensha-asset-card"
              role="button"
              tabindex="0"
              @click="openJubenshaAssetCardEditor(card)"
              @keydown.enter="openJubenshaAssetCardEditor(card)"
              @keydown.space.prevent="openJubenshaAssetCardEditor(card)"
            >
              <div class="asset-card-body">
                <div class="asset-card-content">
                  <div class="asset-card-topline">
                    <span class="asset-id">{{ card.eyebrow }}</span>
                    <button
                      type="button"
                      class="asset-action"
                      title="展开编辑"
                      aria-label="展开编辑"
                      @click.stop="openJubenshaAssetCardEditor(card)"
                    >
                      <WriteIcon />
                    </button>
                  </div>
                  <h3>{{ card.title }}</h3>
                  <p v-for="row in card.rows" :key="row.label">
                    <b>{{ row.label }}</b>{{ row.value }}
                  </p>
                  <div v-if="card.chips?.length" class="detail-chip-list">
                    <span
                      v-for="chip in card.chips"
                      :key="chip"
                      class="detail-chip"
                      >{{ chip }}</span
                    >
                  </div>
                </div>
              </div>
            </article>
          </div>
        </template>
        <div v-else class="empty-state">
          <LayersIcon />
          <h3>还没有开本制作包</h3>
          <p>先在故事页生成席位契约、真相骨架、线索表和轮次压强。</p>
        </div>
      </section>
      <section v-else-if="route === 'assets'" class="page-area workspace-page">
        <div class="workspace-heading">
          <div>
            <span class="eyebrow"
              >ASSET BIBLE /
              {{ dramaProduction?.characters.length || 0 }} CHARACTERS</span
            >
            <h1>故事的视觉基因</h1>
            <p>实体从剧本中长出来，素材提示词保持同一套视觉风格。</p>
            <p>人物、场景和道具均使用稳定编号；分镜提示词直接引用 C001、S001、P001，不引用不存在的图片文件。</p>
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
            {{ tab[1] }} <span>{{ dramaProduction?.[tab[0]].length || 0 }}</span>
          </button>
        </div>
        <div class="asset-grid">
          <article v-for="item in assets" :key="item.id" class="asset-card">
            <div class="asset-card-body">
              <div class="asset-card-content">
                <div class="asset-card-topline">
                  <span class="asset-id">{{ assetIdentity(item) }}</span>
                  <button
                    class="asset-action"
                    type="button"
                    title="编辑资产"
                    @click="openAssetEditor(item)"
                  >
                    <WriteIcon />
                  </button>
                </div>
                <h3>{{ assetKind(item) }} · {{ item.name }}</h3>
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
                <p class="asset-image-references">
                  <b>分镜引用</b>{{ assetReferenceLabel(item) }}
                </p>
              </div>
            </div>
          </article>
        </div>
      </section>
      <section
        v-else-if="route === 'storyboard' && isJubenshaMode"
        class="page-area storyboard-page jubensha-package-page"
      >
        <div class="workspace-heading jubensha-review-heading">
          <div>
            <span class="eyebrow"
              >复盘质检 / {{ jubenshaPackage?.rounds.length || 0 }} 轮</span
            >
            <h1>复盘质检台</h1>
          </div>
        </div>
        <div v-if="jubenshaPackage" class="jubensha-review-shell">
          <div class="matrix-command-bar">
            <div>
              <span class="eyebrow">REVIEW PACKAGE</span>
              <strong>{{ jubenshaPackage.chapter_title }}</strong>
            </div>
            <t-button
              theme="primary"
              :loading="generating"
              @click="generateJubenshaPackage"
              ><WriteIcon />重新生成</t-button
            >
          </div>
          <div class="matrix-subpage-layout jubensha-review-layout">
            <nav class="matrix-section-nav">
              <button
                v-for="tab in jubenshaReviewTabs"
                :key="tab.key"
                class="matrix-section-tab"
                :class="{ active: activeJubenshaReviewTab === tab.key }"
                type="button"
                @click="activeJubenshaReviewTab = tab.key"
              >
                <strong>{{ tab.title }}</strong>
                <span>{{ tab.meta }}</span>
              </button>
            </nav>
            <div class="matrix-section-body">
              <div class="matrix-card-grid">
                <article
                  v-for="card in activeJubenshaReviewCards"
                  :id="jubenshaReviewSectionId(card.key)"
                  :key="card.key"
                  class="novel-panel detail-card matrix-detail-card jubensha-review-card"
                  :class="{ wide: card.wide }"
                >
                  <span class="eyebrow">{{ card.eyebrow }}</span>
                  <h3>{{ card.title }}</h3>
                  <div v-if="card.rows.length" class="detail-rows">
                    <div
                      v-for="row in card.rows"
                      :key="row.label"
                      class="detail-row"
                    >
                      <span>{{ row.label }}</span><strong>{{ row.value }}</strong>
                    </div>
                  </div>
                  <div v-if="card.chips?.length" class="detail-chip-list">
                    <span v-for="chip in card.chips" :key="chip" class="detail-chip">{{
                      chip
                    }}</span>
                  </div>
                  <pre v-if="card.scriptText">{{ card.scriptText }}</pre>
                </article>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <ViewListIcon />
          <h3>还没有复盘内容</h3>
          <p>先在故事页点击“生成开本制作包”。</p>
        </div>
      </section>
      <section
        v-else-if="route === 'storyboard' && isNovelMode"
        class="page-area storyboard-page novel-package-page novel-outline-page"
      >
        <div class="workspace-heading outline-heading">
          <div>
            <span class="eyebrow"
              >大纲追更 / 第 {{ currentChapter?.episode_no || 1 }} 章 · {{ novelPackage?.word_count || chapterDraft.content.length }} 字</span
            >
            <h1>大纲追更台</h1>
          </div>
        </div>
        <div v-if="novelPackage" class="novel-outline-layout">
          <div class="matrix-command-bar">
            <div>
              <span class="eyebrow">OUTLINE PACKAGE</span>
              <strong>{{ novelPackage.chapter_title }}</strong>
            </div>
            <t-button
              theme="primary"
              :loading="generating"
              @click="generateNovelPackage"
              ><WriteIcon />重新生成</t-button
            >
          </div>
          <div class="matrix-subpage-layout novel-outline-board">
            <nav class="matrix-section-nav">
              <button
                v-for="tab in novelOutlineTabs"
                :key="tab.key"
                class="matrix-section-tab"
                :class="{ active: activeNovelOutlineTab === tab.key }"
                type="button"
                @click="activeNovelOutlineTab = tab.key"
              >
                <strong>{{ tab.title }}</strong>
                <span>{{ tab.meta }}</span>
              </button>
            </nav>
            <div class="matrix-section-body">
              <div v-if="activeNovelOutlineTab === 'chapter'" class="novel-check-strip">
                <div v-for="item in novelSerialChecks" :key="item.label" class="novel-check-item">
                  <span>{{ item.label }}</span><strong>{{ item.detail }}</strong>
                </div>
              </div>
              <div class="matrix-card-grid">
                <article
                  v-for="card in activeNovelOutlineCards"
                  :key="card.key"
                  class="novel-panel detail-card matrix-detail-card"
                  :class="{ wide: card.wide }"
                >
                  <span class="eyebrow">{{ card.eyebrow }}</span>
                  <h3>{{ card.title }}</h3>
                  <div class="detail-rows">
                    <div v-for="row in card.rows" :key="row.label" class="detail-row">
                      <span>{{ row.label }}</span><strong>{{ row.value }}</strong>
                    </div>
                  </div>
                  <div v-if="card.chips?.length" class="detail-chip-list">
                    <span v-for="chip in card.chips" :key="chip" class="detail-chip">{{
                      chip
                    }}</span>
                  </div>
                </article>
              </div>
              <article
                v-if="activeNovelOutlineTab === 'chapter'"
                class="novel-panel wide novel-reading-panel novel-chapter-panel matrix-chapter-preview"
              >
                <div>
                  <span class="eyebrow">CHAPTER RELEASE</span>
                  <h3>{{ novelPackage.chapter_title }}</h3>
                  <p>{{ novelPackage.chapter_outline }}</p>
                </div>
                <pre>{{ novelChapterBody }}</pre>
              </article>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <ViewListIcon />
          <h3>还没有大纲</h3>
          <p>先在正文页点击“生成连载方案”。</p>
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
      :header="`建立新${productNoun}`"
      :footer="false"
      :destroy-on-close="true"
      :close-on-overlay-click="true"
      :close-on-esc-keydown="true"
      @close="closeCreateProject"
    >
      <t-form class="create-project-form" @submit="createProject">
        <div class="inline-form-fields">
          <t-form-item label="项目名称"
            ><t-input
              v-model="projectDraft.title"
              :placeholder="isNovelMode ? '例如：重生之长夜破局' : isJubenshaMode ? '例如：钟楼旧宴' : '例如：雨夜归来'"
          /></t-form-item>
          <t-form-item :label="projectGenreLabel"
            ><t-select
              v-model="projectDraft.genre"
              :options="genreOptions"
              filterable
              creatable
              placeholder="选择题材，或输入自定义题材"
              @create="setCustomProjectOption('genre', $event)"
          /></t-form-item>
          <t-form-item :label="projectStyleLabel"
            ><t-select
              v-model="projectDraft.style"
              :options="visualStyleOptions"
              filterable
              creatable
              placeholder="选择风格，或输入自定义风格"
              @create="setCustomProjectOption('style', $event)"
          /></t-form-item>
        </div>
        <t-form-item label="项目简介"
          ><t-textarea v-model="projectDraft.description"
        /></t-form-item>
        <t-button
          theme="primary"
          type="submit"
          block
          :loading="projectCreating"
          :disabled="projectCreating"
          >建立{{ productNoun }}</t-button
        >
      </t-form>
    </t-dialog>
    <t-dialog
      v-model:visible="showCreateChapter"
      :header="`续写第 ${newChapterEpisodeNo} ${chapterUnitLabel}`"
      :footer="false"
      :close-on-overlay-click="!chapterCreating"
      :close-on-esc-keydown="!chapterCreating"
      ><t-form class="create-chapter-form" @submit="draftNextChapter"
        ><section
          v-if="chapterProgress.status !== 'idle'"
          class="quick-progress"
          aria-live="polite"
        >
          <div class="quick-progress-head">
            <strong>{{ chapterProgress.stage }}</strong
            ><span>{{ Math.floor(chapterProgress.percent) }}%</span>
          </div>
          <div class="quick-progress-track">
            <div
              class="quick-progress-fill"
              :class="{ failed: chapterProgress.status === 'failed' }"
              :style="{ width: `${chapterProgress.percent}%` }"
            ></div>
          </div>
          <p class="quick-progress-message">
            {{
              chapterProgress.status === "failed"
                ? chapterProgress.error || chapterProgress.message
                : chapterProgress.message
            }}
          </p>
          <p
            v-if="progressTimingText(chapterProgress)"
            class="quick-progress-message"
          >
            {{ progressTimingText(chapterProgress) }}
          </p>
          <div class="quick-progress-steps">
            <span :class="{ active: chapterProgressTarget >= 8 }">新章节</span
            ><span :class="{ active: chapterProgressTarget >= 30 }">读取前情</span
            ><span :class="{ active: chapterProgressTarget >= 65 }">生成制作包</span>
          </div>
        </section>
        <template v-else>
          <t-form-item label="章节标题"
            ><t-input
              v-model="newChapterForm.title"
              :placeholder="isNovelMode ? '例如：第 2 章 风暴将至' : isJubenshaMode ? '例如：第 2 幕 · 钟声误差' : '例如：第 2 集 · 雨中的证词'" /></t-form-item
          ><t-form-item :label="`本${chapterUnitLabel}剧情方向（可选）`"
          ><t-textarea
              v-model="newChapterForm.brief"
              :placeholder="isNovelMode ? '可填写本章想推进的冲突、爽点或钩子。' : isJubenshaMode ? '可填写本幕想投放的证物、关系压力或复盘信息。' : '可填写本集想重点发展的方向；留空时由 AI 完全参考上一集自动续写。'"
              :autosize="{ minRows: 4, maxRows: 8 }"
          /></t-form-item>
          <p class="settings-hint">
            {{
              isNovelMode
                ? "网文模式可先创建空白章节，再在正文页生成新的制作包。"
                : isJubenshaMode
                  ? "剧本杀模式可先创建空白幕，再在故事页生成新的圆桌回环制作包。"
                  : "留空时，AI 会读取上一集的标题、梗概、正文和结尾状态，在同一项目设定下自动续写。"
            }}
          </p>
          <div class="create-chapter-actions">
            <t-button
              type="button"
              variant="outline"
              :loading="chapterCreating"
              @click="createChapter"
              >创建空白章节</t-button
            ><t-button theme="primary" type="submit" :loading="chapterCreating"
              >AI 自动续写</t-button
            >
          </div>
        </template></t-form
      ></t-dialog
    >
    <t-dialog
      v-model:visible="showDeleteProject"
      header="删除项目"
      class="project-delete-dialog"
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
          type="button"
          variant="outline"
          :disabled="deletingProject"
          @click="
            showDeleteProject = false;
            projectPendingDeletion = null;
          "
          >保留项目</t-button
        ><t-button
          class="project-delete-confirm-button"
          theme="primary"
          type="button"
          :loading="deletingProject"
          @click="deleteProject"
          >确认删除</t-button
        >
      </div>
    </t-dialog>
    <t-dialog
      v-model:visible="showDeleteChapter"
      header="删除章节"
      class="project-delete-dialog"
      :footer="false"
      :close-on-overlay-click="!deletingChapter"
      :close-on-esc-keydown="!deletingChapter"
    >
      <p class="project-delete-confirm">
        删除“{{ chapterPendingDeletion?.title }}”后，该章节正文、制作包和全部资产都会移除，无法恢复。
      </p>
      <div class="project-delete-actions">
        <t-button
          type="button"
          variant="outline"
          :disabled="deletingChapter"
          @click="
            showDeleteChapter = false;
            chapterPendingDeletion = null;
          "
          >保留章节</t-button
        ><t-button
          class="project-delete-confirm-button"
          theme="primary"
          type="button"
          :loading="deletingChapter"
          @click="deleteChapter"
          >确认删除</t-button
        >
      </div>
    </t-dialog>
    <t-dialog
      v-model:visible="showQuickCreate"
      :header="quickCreateLabel"
      :footer="false"
      :close-on-overlay-click="!quickCreating"
      :close-on-esc-keydown="!quickCreating"
    >
      <t-form class="quick-create-form" @submit="createFromOneSentence">
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
          <p v-if="progressTimingText(quickProgress)" class="quick-progress-message">
            {{ progressTimingText(quickProgress) }}
          </p>
          <div class="quick-progress-steps">
            <span :class="{ active: quickProgressTarget >= 15 }">项目</span
            ><span :class="{ active: quickProgressTarget >= 25 }">剧本</span
            ><span :class="{ active: quickProgressTarget >= 60 }"
              >{{ isJubenshaMode ? "开本制作包" : isNovelMode ? "连载方案" : "资产与分镜" }}</span
            >
          </div>
        </section>
        <div class="inline-form-fields">
          <t-form-item label="项目名称"
            ><t-input
              v-model="quickIdea.title"
              :maxlength="quickCreateTitleMaxLength"
              :placeholder="isNovelMode ? '可选，例如：重生之长夜破局' : isJubenshaMode ? '可选，例如：钟楼旧宴' : '可选，例如：雨夜便利店'"
          /></t-form-item>
          <t-form-item v-if="isNovelMode" :label="projectGenreLabel"
            ><t-select
              v-model="quickNovelForm.genre"
              :options="quickNovelGenreOptions"
              filterable
              creatable
              placeholder="选择主题，或输入自定义主题"
            /></t-form-item>
          <t-form-item v-else-if="isJubenshaMode" :label="projectGenreLabel"
            ><t-select
              v-model="quickJubenshaForm.genre"
              :options="quickJubenshaGenreOptions"
              filterable
              creatable
              placeholder="选择剧本类型，或输入自定义类型"
            /></t-form-item>
          <t-form-item v-else :label="projectGenreLabel"
            ><t-select
              v-model="quickDramaForm.genre"
              :options="quickDramaGenreOptions"
              filterable
              creatable
              placeholder="选择题材，或输入自定义题材"
            /></t-form-item>
          <t-form-item v-if="isNovelMode" :label="projectStyleLabel"
            ><t-select
              v-model="quickNovelForm.style"
              :options="quickNovelStyleOptions"
              filterable
              creatable
              placeholder="选择情节标签，或输入自定义标签"
            /></t-form-item>
          <t-form-item v-else-if="isJubenshaMode" :label="projectStyleLabel"
            ><t-select
              v-model="quickJubenshaForm.style"
              :options="quickJubenshaStyleOptions"
              filterable
              creatable
              placeholder="选择故事底色，或输入自定义底色"
            /></t-form-item>
          <t-form-item v-else :label="projectStyleLabel"
            ><t-select
              v-model="quickDramaForm.style"
              :options="quickDramaStyleOptions"
              filterable
              creatable
              placeholder="选择视觉风格，或输入自定义风格"
            /></t-form-item>
        </div>
        <div v-if="isJubenshaMode" class="quick-create-meta-grid">
          <t-form-item label="人数"
            ><t-select
              v-model="quickJubenshaForm.player_count"
              :options="quickJubenshaPlayerCountOptions"
              placeholder="选择人数"
            /></t-form-item>
          <t-form-item label="时间"
            ><t-select
              v-model="quickJubenshaForm.duration"
              :options="quickJubenshaDurationOptions"
              placeholder="选择游戏时间"
            /></t-form-item>
        </div>
        <t-form-item :label="isNovelMode ? '一句话脑洞' : isJubenshaMode ? '一句话开局' : '一句话梗概'"
          ><t-textarea
            v-model="quickIdea.brief"
            :maxlength="quickCreateBriefMaxLength"
            :placeholder="isNovelMode ? '例如：落魄程序员重生到高考前，发现自己的错题本能预测未来热点。' : isJubenshaMode ? '例如：六个旧友在闭馆钟楼重聚，桌上出现一封写给死者的邀请函。' : '例如：一个失忆的快递员在雨夜收到一封来自未来的信。'"
            :autosize="{ minRows: 5, maxRows: 9 }"
        /></t-form-item>
        <t-button
          theme="primary"
          type="submit"
          block
          :loading="quickCreating"
          :disabled="quickCreating"
          ><WriteIcon />{{ isNovelMode ? "生成连载方案" : isJubenshaMode ? "生成开本制作包" : "生成剧本与分镜" }}</t-button
        >
      </t-form>
    </t-dialog>
    <t-dialog
      v-model:visible="showPackageProgress"
      :header="packageButtonLabel"
      :footer="false"
      :close-on-overlay-click="!generating"
      :close-on-esc-keydown="!generating"
      @close="resetPackageProgress"
    >
      <section class="quick-progress" aria-live="polite">
        <div class="quick-progress-head">
          <strong>{{ chapterProgress.stage }}</strong
          ><span>{{ Math.floor(chapterProgress.percent) }}%</span>
        </div>
        <div class="quick-progress-track">
          <div
            class="quick-progress-fill"
            :class="{ failed: chapterProgress.status === 'failed' }"
            :style="{ width: `${chapterProgress.percent}%` }"
          ></div>
        </div>
        <p class="quick-progress-message">
          {{
            chapterProgress.status === "failed"
              ? chapterProgress.error || chapterProgress.message
              : chapterProgress.message
          }}
        </p>
        <p
          v-if="progressTimingText(chapterProgress)"
          class="quick-progress-message"
        >
          {{ progressTimingText(chapterProgress) }}
        </p>
        <div class="quick-progress-steps">
          <span :class="{ active: chapterProgressTarget >= 5 }">校验章节</span
          ><span :class="{ active: chapterProgressTarget >= 30 }">生成制作包</span
          ><span :class="{ active: chapterProgressTarget >= 90 }">保存制作包</span>
        </div>
      </section>
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
      v-model:visible="showPackageEditor"
      :header="`编辑${packageEditContext?.title || '制作内容'}`"
      :footer="false"
      width="720px"
      :close-on-overlay-click="!packageEditSaving"
      :close-on-esc-keydown="!packageEditSaving"
      @close="closePackageEditor"
    >
      <t-form
        v-if="packageEditContext"
        class="asset-editor-form package-editor-form"
        @submit="savePackageEditor"
      >
        <template v-for="field in packageEditContext.fields" :key="field.key">
          <t-form-item :label="field.label">
            <t-textarea
              v-if="field.multiline"
              v-model="field.value"
              :autosize="{ minRows: field.key === 'script_text' ? 7 : 2, maxRows: field.key === 'script_text' ? 18 : 8 }"
            />
            <t-input v-else v-model="field.value" />
          </t-form-item>
        </template>
        <div class="asset-editor-actions">
          <t-button
            type="button"
            variant="outline"
            :disabled="packageEditSaving"
            @click="closePackageEditor"
            >取消</t-button
          >
          <t-button
            type="submit"
            theme="primary"
            :loading="packageEditSaving"
            :disabled="packageEditSaving"
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
                    时，密钥由本机代理管理；饺子矩阵只读取当前供应商和协议状态。
                  </p>
                  <div class="runtime-grid">
                    <div class="runtime-line">
                      <span>当前版本</span><b>v{{ appVersion }}</b>
                    </div>
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
