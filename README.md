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
  将 <strong>飞牛影视 (FNTV)</strong> 中的观看记录自动同步到 <strong>豆瓣书影音档案</strong>，
  让每一部看过的电影和追完的剧集都不留空白。
</p>

<br>

<p align="center">
  <img src="docs/screenshot-dashboard.png" alt="状态面板截图" width="80%" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
</p>

---

## ✨ 功能亮点

| 特性 | 说明 |
|------|------|
| 🚀 **自动同步** | 定时读取飞牛影视播放记录，通过豆瓣 API 自动标记 |
| 🎯 **智能匹配** | 电影自动匹配、电视剧自动识别季度边界，分季正确标记 |
| 📺 **剧集状态机** | 首集 → "在看"，末集 → "看过"，中间集跳过，幂等安全 |
| 🧹 **阈值过滤** | 播放百分比门槛，避免随手点开就标记的误报 |
| ⏰ **灵活调度** | 间隔模式 / Cron 表达式，精确到你想要的每一分钟 |
| 📡 **实时日志** | 浏览器端 SSE 流式展示，每一步操作清晰可见 |
| 🔔 **Bark 推送** | 按状态推送片名、处理结果和失败原因，Cookie 过期主动告警 |
| 🐳 **一键部署** | Docker 镜像即拉即用，无需复杂环境配置 |
| 🌐 **响应式 Web 管理** | 电脑与手机都能使用，浏览器内完成配置、验证和日志查询 |

---

## 🖼️ 界面预览

| 状态面板 | 同步日志 |
|:---:|:---:|
| [![状态面板](docs/screenshot-dashboard.png)](docs/screenshot-dashboard.png) | [![同步日志](docs/screenshot-history.png)](docs/screenshot-history.png) |
| 同步状态一目了然，实时日志逐条展示 | 中文结果、筛选与标题搜索 |

界面所需的 Bootstrap、脚本、Logo 与图标均随项目提供，不依赖外网 CDN；在 NAS 局域网环境中断网也能保持完整排版。

---

## 📋 目录

- [同步规则](#-同步规则)
- [快速开始](#-快速开始)
  - [前提条件](#前提条件)
  - [Docker 部署（推荐）](#docker-部署推荐)
  - [手动部署](#手动部署)
- [配置指南](#-配置指南)
  - [获取豆瓣 Cookie](#获取豆瓣-cookie)
  - [配置项一览](#配置项一览)
- [架构概览](#-架构概览)
- [MoviePilot V3 插件](#-moviepilot-v3-插件)
- [开发指南](#-开发指南)
- [致谢](#-致谢)

---

## 📖 同步规则

<h3>🎬 电影</h3>

飞牛影视已标记「已观看」→ 直接标记「看过」；否则达到设定播放阈值（默认 90%）→ 标记「看过」。低于阈值 → 跳过。

<h3>📺 电视剧</h3>

- **首集** → 标记「在看」
- **中间集** → 跳过，不调用豆瓣 API
- **末集** → 标记「看过」
- **首次同步时所有剧集已完成** → 直接标记「看过」，不经过「在看」
- **同一集重复同步** → 跳过，不会重复标记

<h3>🧠 智能跨季匹配</h3>

当飞牛影视缺少标准季度层级时，系统通过分析集号分布自动检测季度边界（集号回退 = 新季度起点），正确匹配豆瓣的分季条目，避免跨季混淆。

---

## 🚀 快速开始

### 前提条件

- **Docker** + **Docker Compose**（推荐）
- 飞牛影视（FNTV）已正常运行
- 从浏览器提取的豆瓣 Cookie（见下方指南）

### Docker 部署（推荐）

**1. 克隆或下载项目**

```bash
git clone https://github.com/wastedwood/DouBanSync.git
cd DouBanSync
```

**2. 编辑 `docker-compose.yml`**

```yaml
volumes:
  # 飞牛影视数据库文件（只读），根据实际路径修改
  - /vol1/@apps/trimmedia/trimmedia.db:/fntv-db/trimmedia.db:ro
  # 持久化同步状态（自动创建）
  - ./sync_state:/app/sync_state
```

> 飞牛影视数据库通常位于飞牛 OS 的 `/usr/local/apps/@appdata/trim.media/database/trimmedia.db`，`/vol1/@apps/trimmedia/trimmedia.db` 是其符号链接。如有权限问题，请直接挂载原路径。

**3. 拉取并启动**

```bash
docker compose pull   # 拉取最新镜像
docker compose up -d  # 启动容器
```

**4. 打开浏览器配置**

访问 `http://<你的NAS-IP>:58080`，进入配置页：

1. 确认 FNTV 数据库路径（容器内路径 `/fntv-db/trimmedia.db`，挂载正确则无需修改）
2. 粘贴豆瓣 Cookie
3. 选择要同步的飞牛用户
4. 点击「保存配置」

**5. 触发同步**

返回状态面板，点击「立即同步」——右侧实时面板会逐条展示同步过程。

> 💡 **首次同步后**：系统会根据你设定的调度计划自动运行，无需手动干预。

### 手动部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python -m app
```

默认监听 `http://0.0.0.0:5000`。

---

## ⚙️ 配置指南

### 获取豆瓣 Cookie

<details>
<summary>📝 点击展开详细步骤</summary>

1. 使用浏览器打开 [movie.douban.com](https://movie.douban.com/) 并登录你的账号
2. 按 **F12** 打开开发者工具，切换到 **Network（网络）** 标签页
3. 刷新页面
4. 在请求列表中找到第一个 `movie.douban.com` 的 document 类型请求
5. 在 **Request Headers** 中找到 `Cookie:` 这一行
6. **右键 → Copy Value** 复制整段 Cookie 字符串
7. 粘贴到 DouBanSync 配置页面的 Cookie 输入框中

> ⚠️ 豆瓣 Cookie 有有效期，过期后需要重新提取。应用会在遇到 403 时自动尝试刷新，但长期不活跃仍需手动更新。
</details>

### 配置项一览

| 配置 | 说明 | 默认值 |
|------|------|--------|
| **FNTV 数据库路径** | 容器内数据库文件路径 | `/fntv-db/trimmedia.db` |
| **同步用户** | 选择要同步的飞牛用户 | — |
| **豆瓣 Cookie** | 浏览器提取的完整 Cookie 字符串 | — |
| **同步计划** | 间隔模式（每 N 小时）或 Cron 表达式（带可视化构建器） | 每 24 小时 |
| **播放阈值** | 支持自定义，超过设定百分比才算已看（0 为不限制） | 90% |
| **仅自己可见** | 豆瓣标记是否仅自己可见 | 是 |
| **Bark Key** | iOS 推送设备标识，留空禁用（从 Bark App 复制） | 空 |

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   Web UI                             │
│           (Jinja2 + Bootstrap 5)                     │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────────────┐
│                  routes.py                           │
│              (Flask Blueprint)                       │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              sync_engine.py                          │
│         ◄── event_bus.py (SSE 实时推送)               │
└──────┬───────────────────────────┬──────────────────┘
       │                           │
┌──────▼──────────┐     ┌─────────▼──────────┐
│   fntv_db.py    │     │  douban_client.py  │
│  (FNTV 只读层)   │     │  (豆瓣 API 封装)    │
└──────┬──────────┘     └─────────┬──────────┘
       │                          │
┌──────▼──────────┐     ┌─────────▼──────────┐
│   FNTV SQLite   │     │   豆瓣非官方 API    │
│   （只读挂载）    │     │   (Cookie 认证)     │
└─────────────────┘     └────────────────────┘

┌─────────────────────────────────────────────────────┐
│              sync_store.py → sync_state.db          │
│         (SQLite + WAL — 状态持久化)                    │
└─────────────────────────────────────────────────────┘
```

### 数据流

1. **调度器**触发同步 → `sync_engine` 启动
2. 从 **FNTV SQLite** 读取增量播放记录（只读）
3. 按规则 **分类**：电影 / 剧集
4. **搜索豆瓣**匹配条目标题
5. **标记状态**（在看 / 看过）
6. 记录结果到 **sync_state.db**
7. 全程通过 **Event Bus + SSE** 实时推送到浏览器

---

## 🛠️ 开发指南

```bash
# 克隆项目
git clone https://github.com/wastedwood/DouBanSync.git
cd DouBanSync

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python -m app
```

> 开发服务器默认监听 `http://0.0.0.0:5000`。
> Docker 部署的访问地址为 `http://<你的NAS-IP>:58080`。

### 项目结构

```
DouBanSync/
├── app/                    # 应用核心
│   ├── __init__.py         # Flask 应用工厂 + 调度器
│   ├── __main__.py         # 入口点
│   ├── config.py           # 配置管理
│   ├── douban_client.py    # 豆瓣 API 封装
│   ├── event_bus.py        # 事件总线（SSE 实时日志）
│   ├── fntv_db.py          # 飞牛 SQLite 只读访问
│   ├── routes.py           # Web 路由 + API 端点
│   ├── sync_engine.py      # 同步主编排引擎
│   ├── sync_store.py       # 同步状态持久化
│   ├── static/              # 本地样式、脚本、Logo 与 Bootstrap
│   └── templates/          # 页面模板
├── sync_state/             # 运行时数据
├── config.yaml             # 默认配置
├── docker-compose.yml      # Docker 编排
├── Dockerfile              # 容器构建
├── requirements.txt        # Python 依赖
└── README.md               # 本文件
```

---

## 🧩 MoviePilot V3 插件

项目同时提供可被 MoviePilot V3 加载的插件目录：`plugins.v3/doubansync`。插件保留原有同步核心，使用 MoviePilot 的配置表单、公共调度器、详情页 API 和插件数据目录；原来的 Flask/Docker 入口不受影响。

使用方式：

1. 将 [wastedwood/MoviePilot-Plugins](https://github.com/wastedwood/MoviePilot-Plugins) 加入 MoviePilot 的插件市场仓库配置。
2. 安装「飞牛影视同步豆瓣」插件。
3. 在插件配置中填写 MoviePilot 容器内的 FNTV 数据库路径、豆瓣 Cookie，并选择用户。
4. 开启插件后保存；可勾选「保存后立即同步一次」进行首次验证。

如果 MoviePilot 使用 Docker，需将 FNTV 数据库只读挂载到 MoviePilot 容器，例如：

```yaml
volumes:
  - /宿主机路径/trimmedia.db:/fntv-db/trimmedia.db:ro
```

插件内对应填写 `/fntv-db/trimmedia.db`。插件自己的 `sync_state.db` 会写入 MoviePilot 插件数据目录，不会修改飞牛影视数据库。V3 插件的详细文件和兼容边界见 [`plugins.v3/doubansync/README.md`](plugins.v3/doubansync/README.md)。

---

## 🤝 致谢

- [MoviePilot-Plugins / doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching) — 豆瓣 Cookie 认证与标记接口的参考实现
- [fntv-record-view](https://github.com/QiaoKes/fntv-record-view) — FNTV 数据库只读查询与播放记录分析的参考实现
- 感谢所有使用和反馈的用户 ❤️

---

<p align="center">
  <sub>Built with ❤️ for the FNTV &amp; Douban community</sub>
  <br>
  <sub>如果你喜欢这个项目，欢迎 ⭐️ Star 支持</sub>
</p>
