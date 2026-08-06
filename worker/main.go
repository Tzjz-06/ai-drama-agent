package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/hibiken/asynq"
)

type taskPayload struct {
	ID        string         `json:"id"`
	ProjectID string         `json:"project_id"`
	ChapterID string         `json:"chapter_id"`
	Type      string         `json:"type"`
	Payload   map[string]any `json:"payload"`
	Provider  *providerConfig `json:"provider,omitempty"`
}

type providerConfig struct {
	Category string `json:"category"`
	APIURL   string `json:"api_url"`
	APIKey   string `json:"api_key"`
	Model    string `json:"model"`
}

func main() {
	redisAddr := env("AI_DRAMA_REDIS_ADDR", "redis:6379")
	if env("AI_DRAMA_WORKER_MODE", "worker") == "gateway" {
		runGateway(redisAddr)
		return
	}
	server := asynq.NewServer(
		asynq.RedisClientOpt{Addr: redisAddr, Password: os.Getenv("AI_DRAMA_REDIS_PASSWORD")},
		asynq.Config{Concurrency: 4, Queues: map[string]int{"default": 10}},
	)
	mux := asynq.NewServeMux()
	mux.HandleFunc("jiaozi:frame_image", handleProviderTask("AI_DRAMA_IMAGE_API_URL", "关键帧"))
	mux.HandleFunc("jiaozi:asset_image", handleProviderTask("AI_DRAMA_IMAGE_API_URL", "资产素材"))
	mux.HandleFunc("jiaozi:video", handleProviderTask("AI_DRAMA_VIDEO_API_URL", "视频"))
	mux.HandleFunc("jiaozi:merge", handleMergeTask)
	if err := server.Run(mux); err != nil {
		panic(err)
	}
}

func runGateway(redisAddr string) {
	client := asynq.NewClient(asynq.RedisClientOpt{Addr: redisAddr, Password: os.Getenv("AI_DRAMA_REDIS_PASSWORD")})
	defer client.Close()

	http.HandleFunc("/health", func(response http.ResponseWriter, request *http.Request) {
		writeJSON(response, http.StatusOK, map[string]any{"ok": true})
	})
	http.HandleFunc("/enqueue", func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodPost {
			writeJSON(response, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
			return
		}
		defer request.Body.Close()
		var payload taskPayload
		if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "invalid JSON payload"})
			return
		}
		if payload.ID == "" || payload.Type == "" {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "id and type are required"})
			return
		}
		if payload.Type != "frame_image" && payload.Type != "asset_image" && payload.Type != "video" && payload.Type != "merge" {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "unsupported task type"})
			return
		}
		encoded, err := json.Marshal(payload)
		if err != nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": err.Error()})
			return
		}
		info, err := client.Enqueue(
			asynq.NewTask("jiaozi:"+payload.Type, encoded),
			asynq.Queue("default"),
			asynq.TaskID(payload.ID),
			asynq.Retention(24*time.Hour),
		)
		if err != nil {
			writeJSON(response, http.StatusServiceUnavailable, map[string]any{"error": err.Error()})
			return
		}
		writeJSON(response, http.StatusAccepted, map[string]any{"ok": true, "id": info.ID, "queue": info.Queue})
	})
	http.HandleFunc("/tasks/", func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			writeJSON(response, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
			return
		}
		taskID := strings.TrimPrefix(request.URL.Path, "/tasks/")
		if taskID == "" {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "task id is required"})
			return
		}
		inspector := asynq.NewInspector(asynq.RedisClientOpt{Addr: redisAddr, Password: os.Getenv("AI_DRAMA_REDIS_PASSWORD")})
		defer inspector.Close()
		info, err := inspector.GetTaskInfo("default", taskID)
		if err != nil {
			writeJSON(response, http.StatusNotFound, map[string]any{"error": err.Error()})
			return
		}
		status := normalizeTaskState(fmt.Sprint(info.State))
		result := map[string]any{}
		if len(info.Result) > 0 {
			_ = json.Unmarshal(info.Result, &result)
		}
		writeJSON(response, http.StatusOK, map[string]any{
			"id": taskID,
			"status": status,
			"progress": taskProgress(status),
			"message": taskMessage(status, info.LastErr),
			"result": result,
		})
	})

	address := env("AI_DRAMA_GATEWAY_ADDR", ":8787")
	if err := http.ListenAndServe(address, nil); err != nil {
		panic(err)
	}
}

func writeJSON(response http.ResponseWriter, status int, payload map[string]any) {
	response.Header().Set("Content-Type", "application/json; charset=utf-8")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(payload)
}

func handleProviderTask(envKey string, label string) asynq.HandlerFunc {
	return func(ctx context.Context, task *asynq.Task) error {
		var payload taskPayload
		if err := json.Unmarshal(task.Payload(), &payload); err != nil {
			return fmt.Errorf("解析 %s 任务失败: %w", label, asynq.SkipRetry)
		}
		endpoint := strings.TrimSpace(os.Getenv(envKey))
		apiKey := providerKey(envKey)
		model := ""
		if payload.Provider != nil {
			endpoint = strings.TrimSpace(payload.Provider.APIURL)
			apiKey = strings.TrimSpace(payload.Provider.APIKey)
			model = strings.TrimSpace(payload.Provider.Model)
		}
		if endpoint == "" {
			return fmt.Errorf("%s 生成服务未配置，请设置 %s: %w", label, envKey, asynq.SkipRetry)
		}
		prompt, ok := payload.Payload["prompt"].(string)
		if !ok || strings.TrimSpace(prompt) == "" {
			return fmt.Errorf("%s 任务缺少 prompt: %w", label, asynq.SkipRetry)
		}
		body := map[string]any{"prompt": prompt}
		for _, key := range []string{"negative_prompt", "duration_seconds", "shot_id", "model"} {
			if value, exists := payload.Payload[key]; exists {
				body[key] = value
			}
		}
		if model != "" {
			body["model"] = model
		}
		encoded, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("编码 %s 请求失败: %w", label, err)
		}
		request, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(encoded))
		if err != nil {
			return fmt.Errorf("创建 %s 请求失败: %w", label, err)
		}
		request.Header.Set("Content-Type", "application/json")
		if apiKey != "" {
			request.Header.Set("Authorization", "Bearer "+apiKey)
		}
		response, err := (&http.Client{Timeout: 10 * time.Minute}).Do(request)
		if err != nil {
			return fmt.Errorf("%s 服务连接失败: %w", label, err)
		}
		defer response.Body.Close()
		responseBody, _ := io.ReadAll(io.LimitReader(response.Body, 2<<20))
		if response.StatusCode >= 300 {
			if response.StatusCode < 500 {
				return fmt.Errorf("%s 服务返回 HTTP %d: %s: %w", label, response.StatusCode, strings.TrimSpace(string(responseBody)), asynq.SkipRetry)
			}
			return fmt.Errorf("%s 服务返回 HTTP %d: %s", label, response.StatusCode, strings.TrimSpace(string(responseBody)))
		}
		var providerResponse map[string]any
		if err := json.Unmarshal(responseBody, &providerResponse); err != nil {
			return fmt.Errorf("%s 服务返回不是合法 JSON: %w", label, err)
		}
		mediaURL := extractURL(providerResponse)
		if mediaURL == "" {
			return fmt.Errorf("%s 服务响应缺少 url；供应商适配器契约要求返回 {\"url\":\"...\"}", label)
		}
		result, _ := json.Marshal(map[string]any{"url": mediaURL})
		_, err = task.ResultWriter().Write(result)
		return err
	}
}

func handleMergeTask(ctx context.Context, task *asynq.Task) error {
	var payload taskPayload
	if err := json.Unmarshal(task.Payload(), &payload); err != nil {
		return fmt.Errorf("解析视频合成任务失败: %w", err)
	}
	clips, ok := payload.Payload["clips"].([]any)
	if !ok || len(clips) == 0 {
		return fmt.Errorf("视频合成任务缺少 clips 输入片段")
	}
	ffmpegPath := env("FFMPEG_BIN", "ffmpeg")
	output := env("AI_DRAMA_OUTPUT_VIDEO", "/data/outputs/"+payload.ID+".mp4")
	args := []string{"-y"}
	for _, raw := range clips {
		clip, valid := raw.(map[string]any)
		if !valid || strings.TrimSpace(fmt.Sprint(clip["path"])) == "" {
			return fmt.Errorf("视频合成任务包含无效片段")
		}
		args = append(args, "-i", fmt.Sprint(clip["path"]))
	}
	args = append(args, "-filter_complex", "concat=n="+fmt.Sprint(len(clips))+":v=1:a=1[outv][outa]", "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-c:a", "aac", output)
	command := exec.CommandContext(ctx, ffmpegPath, args...)
	if outputBytes, err := command.CombinedOutput(); err != nil {
		return fmt.Errorf("FFmpeg 合成失败: %s: %w", strings.TrimSpace(string(outputBytes)), err)
	}
	result, _ := json.Marshal(map[string]any{"url": output})
	_, err := task.ResultWriter().Write(result)
	return err
}

func providerKey(endpointKey string) string {
	if endpointKey == "AI_DRAMA_IMAGE_API_URL" {
		return strings.TrimSpace(os.Getenv("AI_DRAMA_IMAGE_API_KEY"))
	}
	return strings.TrimSpace(os.Getenv("AI_DRAMA_VIDEO_API_KEY"))
}

func extractURL(payload map[string]any) string {
	if value, ok := payload["url"].(string); ok {
		return strings.TrimSpace(value)
	}
	if items, ok := payload["data"].([]any); ok && len(items) > 0 {
		if item, ok := items[0].(map[string]any); ok {
			if value, ok := item["url"].(string); ok {
				return strings.TrimSpace(value)
			}
		}
	}
	return ""
}

func normalizeTaskState(state string) string {
	switch state {
	case "pending", "scheduled":
		return "queued"
	case "retry":
		return "retrying"
	case "active":
		return "running"
	case "completed":
		return "completed"
	case "archived", "failed":
		return "failed"
	default:
		return "degraded"
	}
}

func taskProgress(status string) int {
	if status == "completed" { return 100 }
	if status == "running" { return 50 }
	return 0
}

func taskMessage(status string, lastError string) string {
	if (status == "retrying" || status == "failed") && strings.TrimSpace(lastError) != "" { return lastError }
	return map[string]string{"queued": "等待 Asynq worker 领取", "retrying": "worker 将重试任务", "running": "worker 正在处理", "completed": "任务已完成", "failed": "任务失败", "degraded": "任务状态未知"}[status]
}

func env(key string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
