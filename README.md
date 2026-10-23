<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
</p>

<p align="center"><img src="app/static/img/brand-mark.svg" alt="DouBanSync Logo" width="68"></p>
<h1 align="center">DouBanSync</h1>
<h3 align="center">飞牛影视 → 豆瓣 · 观看记录自动同步工具</h3>

<p align="center">
  将 <strong>飞牛影视 (FNTV)</strong> 中的观看记录增量、自动同步到 <strong>豆瓣</strong>（标记「在看」与「看过」），零侵入安全只读。
</p>

---

## ✨ 核心特性

- 🚀 **自动增量同步**：定时读取飞牛影视播放记录，通过豆瓣 API 自动标记状态。
- 🎯 **智能分季匹配**：解析豆瓣全部搜索结果，支持多候选精确选季与集数回退跨季推断，杜绝误命中第 1 季。
- 📺 **追剧状态机**：首集 →「在看」，完结 →「看过」，中间集跳过豆瓣请求，幂等防风控。
- 🛡️ **安全只读机制**：使用临时数据库副本 + `mode=ro` 只读连接，绝不修改飞牛原始库。
- 🧹 **进度阈值过滤**：支持自定义播放百分比门槛（默认 90%），防止随手点开导致误标。
- ⏰ **双调度模式**：支持固定小时间隔与自定义 Cron 表达式。
- 🔔 **Bark 实时推送**：状态变更精准通知，Cookie 过期主动预警。
- 🌐 **响应式 Web 管理**：内置开箱即用的 Web 界面与 SSE 实时同步日志，无需外网 CDN。

---

## 🚀 快速开始 (Docker Compose)

### 1. 编写 `docker-compose.yml`

```yaml
services:
  doubansync:
    image: wastedwood/doubansync:latest
    container_name: doubansync
    restart: unless-stopped
    ports:
      - "58080:5000"
    volumes:
      # 飞牛数据库路径（只读挂载）
      - /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro
      # 状态数据持久化目录
      - ./sync_state:/app/sync_state
    environment:
      - TZ=Asia/Shanghai
```

> **提示**：以上为飞牛影视数据库的默认位置，若你的路径不同，替换冒号左侧部分即可。

### 2. 启动与配置

```bash
docker compose up -d
```

1. 打开浏览器访问 `http://<NAS_IP>:58080` 进入配置页；
2. 粘贴从浏览器提取的 **豆瓣 Cookie** 并选择要同步的飞牛用户；
3. 保存后点击「立即同步」即可开始首次同步。

---

## 📖 同步规则速查

| 类别 | 触发条件 | 豆瓣标记状态 |
|------|----------|--------------|
| **电影** | 飞牛标记「已看」或播放进度 ≥ 设定阈值 | `看过` (collect) |
| **电视剧·首集** | 首次开始观看该季 | `在看` (do) |
| **电视剧·中间集** | 观看进度推进 | 本地记录进度，**跳过豆瓣 API** |
| **电视剧·完结** | 达到该季总集数或一次性看完 | `看过` (collect) |

---

## ⚙️ 核心配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| **FNTV 数据库路径** | 容器内只读数据库文件路径 | `/fntv-db/trimmedia.db` |
| **豆瓣 Cookie** | 从浏览器提取的完整 Cookie 字符串（包含 `dbcl2` 与 `ck`） | — |
| **同步计划** | 间隔模式（每 N 小时）或 Cron 表达式（如 `0 3 * * *`） | 每 24 小时 |
| **播放阈值** | 达到该播放百分比后才触发同步（0 为不限制） | 90% |
| **仅自己可见** | 豆瓣标记是否设为私密 | 是 |
| **Bark Key** | iOS Bark 推送设备 Key（留空禁用） | 空 |

---

## 🗺️ 待办与规划 (TBD)

- [ ] **MoviePilot 插件适配**：提供独立插件包并发布至 MoviePilot 插件市场。

---

## 🤝 致谢

- 参考项目：[MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching) & [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)
