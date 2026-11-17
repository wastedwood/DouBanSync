<p align="center"><img src="app/static/img/brand-mark.svg" alt="DouBanSync" width="68"></p>
<h1 align="center">DouBanSync</h1>
<p align="center">把飞牛影视（FNTV）的观看记录自动同步到豆瓣。</p>

---

## 特性

- 只读挂载飞牛影视数据库，不改动原库数据
- 增量同步电影与剧集的「在看」「看过」状态，标记默认仅自己可见
- 支持按间隔或 Cron 定时同步，Web 界面可查看实时进度与历史日志
- 可选自动移除豆瓣「想看」中飞牛库已有的影片，支持 Bark 推送同步结果与 Cookie 过期提醒

## 部署

### 1. 创建 `docker-compose.yml`

```yaml
services:
  fntv-douban-sync:
    image: wastedwood/doubansync:latest
    container_name: fntv-douban-sync
    restart: unless-stopped
    ports:
      - "58080:5000"
    volumes:
      - /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro
      - ./sync_state:/app/sync_state
    environment:
      - TZ=Asia/Shanghai
      - FNTV_DB_PATH=/fntv-db/trimmedia.db
```

### 2. 启动并配置

```bash
docker compose up -d
```

打开 `http://<NAS_IP>:58080/config`，选择同步用户并粘贴豆瓣 Cookie（页面内附图文获取指南），保存后在状态面板点击「立即同步」。可在同一页面按需调整播放阈值、定时计划、隐私设置与 Bark 推送。

### 3. 升级

```bash
docker compose pull && docker compose up -d
```

## 同步规则

- **电影**：播放进度达到阈值（默认 `90%`）记为「看过」，有进度但未达到记为「在看」；阈值设为 `0%` 时，有进度即算看完。
- **剧集**：按季同步。开始观看任意一集记为「在看」，看完该季最后一集才记为「看过」；最后一集取本地入库数与刮削计划集数的较大值，追更中的季不会提前标为看过。第 0 季（特别篇）不同步。
- **多季匹配**：每季对应豆瓣独立条目，支持按季号、季标题（如「最终季」「千年血战篇」）及「剧名 + 数字」匹配，也兼容一季拆分为多个豆瓣条目的情况。匹配不到直接记为失败，不误标到第一季，可在「同步日志」查看后手动处理。
- **容错与重试**：豆瓣接口临时超时或返回 5xx 时，同步进度不会越过失败记录，下次同步自动重试；Cookie 过期后在配置页重新保存即可恢复。

## 致谢

- [MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)
- [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)
