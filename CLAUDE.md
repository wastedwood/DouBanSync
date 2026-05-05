# DouBanSync — 项目规范

## 项目定位

飞牛影视(FNTV) → 豆瓣 观看记录自动同步工具。

## 目录结构

```
DouBanSync/
├── app/                    # 应用核心
│   ├── __init__.py         # Flask 应用工厂 + APScheduler 启动
│   ├── __main__.py         # 入口点 (python -m app)
│   ├── config.py           # 配置管理器（YAML + runtime_config 两级）
│   ├── douban_client.py    # 豆瓣非官方 API 封装（Cookie 认证 + 搜索 + 标记）
│   ├── event_bus.py        # 线程安全事件总线（SSE 实时日志用）
│   ├── fntv_db.py          # 飞牛影视 SQLite 只读访问层
│   ├── routes.py           # Web 路由 + JSON API + SSE 端点
│   ├── sync_engine.py      # 同步主编排引擎
│   ├── sync_store.py       # 同步状态持久化（SQLite + WAL）
│   └── templates/          # Jinja2 模板
│       ├── base.html
│       ├── config.html
│       ├── cookie_guide.html
│       ├── dashboard.html
│       └── history.html
├── sync_state/             # 运行时数据（由应用创建）
│   └── sync_state.db       # SQLite: 状态表 + 日志表 + config 表
├── config.yaml             # 默认配置（可被运行时配置覆盖）
├── .dockerignore            # Docker 构建上下文排除规则
├── docker-compose.yml      # Docker 编排
├── Dockerfile              # python:3.13-alpine 构建
├── requirements.txt        # pip 依赖
├── CLAUDE.md               # 本文件
└── README.md               # 用户文档
```

## 架构分层

```
Web UI (Jinja2 + Bootstrap 5)
   ↓ HTTP / SSE
routes.py (Flask Blueprint)
   ↓
sync_engine.py  ←  event_bus.py (实时推送)
   ↓        ↓
fntv_db.py  douban_client.py
   ↓        ↓
FNTV SQLite  豆瓣非官方 API
```

状态持久化通过 sync_store.py → SQLite (WAL 模式)。

## 关键约定

### 同步流程
1. 播放百分比阈值过滤
2. 分类（电影 / 剧集），剧集优先走标准层级，回退智能跨季推断
3. 搜索豆瓣 → 标记状态
4. 更新 last_sync_time

### 电视剧状态机
```
pending → doing（首集） → done（末集）
       ↘ done（已看完才首次同步）
doing + 中间集 → 跳过（不调用豆瓣 API）
done → 跳过幂等
```

### 配置优先级
环境变量 > 运行时配置（runtime_config 表） > config.yaml 默认值

### 路由清单

页面：
- `GET /` — 状态面板
- `GET /config` — 配置页
- `GET /history` — 同步日志
- `GET /cookie-guide` — Cookie 提取指南

API：
- `GET /api/sync/stream` — SSE 实时事件流
- `POST /api/sync/run` — 触发同步
- `GET /api/sync/status` — 同步状态
- `GET /api/fntv/users` — 用户列表
- `POST /api/fntv/test-db` — 数据库验证
- `POST /api/douban/check-cookie` — Cookie 验证
- `GET /api/config` — 获取当前配置（JSON）
- `GET /api/stats` — 同步统计

### 环境变量

| 变量 | 用途 |
|------|------|
| `FNTV_DB_PATH` | 覆盖 config.yaml 的数据库路径 |
| `SYNC_STATE_DIR` | 运行时数据目录（默认 ../sync_state） |

### 智能跨季推断策略（fntv_db.py:detect_season_groups）

优先走 `episode→season→series` 标准层级；失败时回退到 `episode→series` 扁平结构，
通过分析全量 episode_number 的分布检测季度边界（数值回退 = 新季度）。

### 播放百分比阈值

在 `sync_engine._do_run()` 中计算 `play.position_seconds / (item.runtime_minutes * 60)`，
低于 `watch_threshold_percent` 的跳过（runtime 缺失时不拦截）。

### Cookie 处理模式

参考 [MoviePilot DoubanHelper](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)：
- Cookie 来源：手动输入，SimpleCookie 解析
- `_refresh_ck()` / `set_ck()` 只在 ck 缺失或 403 重试时调用，不每次验证都刷新
- 无专门 auth 验证步骤——直接用 Cookie 操作，遇到 403 刷新 ck 后重试一次
- 标记接口 403 → 刷新 ck → 重试一次，仍失败才返回 False

### 豆瓣搜索兼容

豆瓣搜索页存在多种链接格式，`_parse_search_result` 按优先级尝试：
- 格式 A：直接链接 `subject/ID/`
- 格式 B：跟踪链接 `link2/?url=...subject%2FID%2F...`（当前主流）
- 格式 C：`onclick` 属性中的 `sid: ID`

## 参考项目

### [MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)

豆瓣同步插件的参考实现，核心文件 `DoubanHelper.py`：

| 模式 | 做法 |
|------|------|
| Cookie 管理 | 静态 Cookie 字符串，SimpleCookie 解析 |
| ck 刷新 | `set_ck()` GET 豆瓣首页，从 Set-Cookie 提取新 ck，只在缺失或 403 时调用 |
| 搜索 | `get_subject_id(title)` → `/search?cat=1002` → BeautifulSoup 解析 `div.title > a` |
| 标记 | `set_watching_status(sid, status)` → POST `/j/subject/{sid}/interest` → 403 时刷 ck 重试 |
| 状态值 | `do`（在看）、`doing`（想看已纠正场）、`done`（看过）→ 对应 collect |
| 代理 | 全局 `self.proxies` 参数，透传到所有 requests 调用 |
| 死信重试 | `_wait_process` 字典持久化，每次成功同步后重试失败项 |

### [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)

FNTV 播放记录查看器，核心文件 `main.py`：

| 层面 | 做法 |
|------|------|
| 数据库访问 | SQLite `mode=ro` 只读连接，不挂载写权限 |
| 层级查询 | **递归 CTE** 解析媒体树形层级，带深度限制防死循环 |
| 播放进度 | `position / duration` 计算百分比，转为 `hh:mm:ss` 格式显示 |
| 分页 | `LIMIT/OFFSET` 标准分页 |
| 查询优化 | `functools.lru_cache` 或简单字典缓存减少重复查询 |
| 安全 | 参数化查询防注入，错误日志记录不泄露路径 |

## 验证

```bash
python -m app                    # 启动开发服务器
# 打开 http://localhost:5000 手动验证
```

## 红线

- 不修改飞牛影视数据库（只读挂载 + 临时副本）
- 豆瓣 Cookie 不进 git
- 不创建新的数据库表（只读 trimmedia.db）
