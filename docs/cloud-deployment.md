# 云端双端部署

这套部署让电脑和手机访问同一个 HTTPS 地址，共用云端 `LocalStore` 数据文件。手机端打开后可以通过浏览器的“添加到主屏幕”安装成 App。

## 1. 准备域名

把域名的 DNS `A` 记录指向云主机公网 IP，并确认云主机安全组放行 TCP `80` 和 `443`。

## 2. 配置环境

在项目根目录复制 `.env.example` 为 `.env`，填写域名和模型配置。`.env` 已被 git 忽略，不会进入镜像或前端 bundle。

## 3. 启动

```bash
docker compose --env-file .env -f docker-compose.cloud.yml up -d --build
```

Caddy 会自动申请和续期 HTTPS 证书。浏览器打开 `https://你的域名/`，注册一个账户；电脑和手机使用同一个账户即可看到同一份项目。

## 4. 更新与备份

更新代码后重复执行上面的命令。项目、章节和登录会话保存在 Docker volume `app_data`，可以定期备份：

```bash
docker run --rm -v ai-drama-agent_app_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/app-data-$(date +%F).tgz -C /data .
```

生成任务使用服务端配置的模型接口，浏览器不会接触 `AI_DRAMA_API_KEY`。没有填写模型密钥时，容器会拒绝启动，避免云端静默进入离线模式。
