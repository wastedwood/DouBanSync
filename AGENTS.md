# DouBanSync — 项目规范

飞牛影视(FNTV) → 豆瓣 观看记录自动同步工具。

## 目录结构

```
app/
├── __init__.py         # Flask 应用工厂 + APScheduler 调度
├── __main__.py         # 入口 (python -m app)
├── config.py           # 配置：环境变量 > runtime_config 表 > config.yaml
├── douban_client.py    # 豆瓣非官方接口：Cookie 认证、搜索选条目、标记状态
├── event_bus.py        # 线程安全事件总线（SSE 实时日志）
├── fntv_db.py          # 飞牛 SQLite 只读访问层（临时副本 + mode=ro）
├── notifier.py         # Bark 推送
├── routes.py           # 页面 + JSON API + SSE
├── sync_engine.py      # 同步编排
├── sync_store.py       # 同步状态 / 日志 / 运行时配置（SQLite WAL）
├── static/             # 前端 JS/CSS + 本地化 Bootstrap
└── templates/          # Jinja2 模板
tests/                  # unittest 用例
.github/workflows/      # 推送 v* 标签时构建并推送 Docker Hub 镜像
```

运行时数据在 `sync_state/sync_state.db`（`SYNC_STATE_DIR` 可覆盖），不入库。

## 同步流程

1. 增量读取 `last_sync_time` 之后的播放记录
2. 播放百分比阈值过滤（`watched` 标记优先；runtime 缺失不拦截）
3. 播放指纹未变化则跳过豆瓣调用
4. 分类：电影 / 剧集。剧集走 `episode→season→series` 标准层级，失败回退扁平结构推断
5. 搜索豆瓣 → 标记状态 → 更新 `last_sync_time`

升级后的一次性修复（`_repair_*`，以 runtime_config 中的 marker 保证只跑一次，有失败则下次重试）：
- `_repair_legacy_done`：旧版本 done 未生效的条目重新标记
- `_repair_season_subjects`：第 2 季及以后误配到第一季条目的记录，重新搜索到不同条目才改标

### 电视剧状态机

```
pending → doing（首集） → done（末集）
       ↘ done（已看完才首次同步）
doing + 中间集 → 跳过（不调用豆瓣 API）
done → 跳过（幂等）
```

状态按 `(series_guid, season_number)` 聚合。第 0 季（特别篇）不同步。

### 多季匹配规则

- 季度：`SyncEngine._resolve_season`。剧名自带季度（续作独立入库，如「庆余年 第二季」）且飞牛季号为 1 / 空时，以剧名为准
- 搜索词：第 2 季及以后带季度标签（「X 第二季」）；标准层级第一季只搜剧名
- 选条目：`DoubanClient._select_best_candidate`
  - 第 2 季及以后：季度与剧名必须同时匹配，否则返回无结果（宁可失败，不误标）
  - 第一季 / 电影：排除第 2 季及以后，优先剧名一致
- 季度解析：`extract_season_info` 识别「第N季」「Season N」「SNN」；不识别「马大帅2」这类数字后缀

### 飞牛数据特征（实测）

- 剧集基本都是标准层级；`episode` 直接挂在 `series` 下的扁平结构未见，扁平推断（`detect_season_groups`）基本不会触发
- 重新刮削会遗留父节点已不存在的 `episode` / `season`，这类记录取不到层级，会被跳过
- `item.douban_id` 在季层级不可靠（多季常共用第一季 ID），不使用

## 豆瓣接口

- Cookie 手动输入，`SimpleCookie` 解析；`ck` 只在缺失或 403 时刷新，403 后重试一次
- 内部状态 `doing`/`done` 映射为豆瓣 `do`/`collect`，标记后回读核对实际状态
- 搜索页链接格式按优先级解析：`subject/ID/` → `link2/?url=...` → `onclick` 中的 `sid`

## 路由

页面：`/`、`/config`、`/history`、`/cookie-guide`

API：`GET /api/sync/stream`（SSE）、`POST /api/sync/run`、`GET /api/sync/status`、`GET /api/fntv/users`、`POST /api/fntv/test-db`、`POST /api/douban/check-cookie`、`GET /api/config`、`GET /api/stats`、`POST /api/bark/test`

## 验证

```bash
python -m pytest -q   # 单元测试
python -m app         # 开发服务器，http://localhost:5000
```

## 发布

改版本时同步更新 `CHANGELOG.md`、`app/templates/base.html` 侧栏版本号与 `tests/test_frontend.py`。推送 `vX.Y.Z` 标签触发镜像构建。

## 红线

- 不修改飞牛影视数据库（只读挂载 + 临时副本）
- 豆瓣 Cookie 不进 git

## 参考项目

- [MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)：Cookie / ck 刷新 / 搜索与标记接口
- [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)：飞牛数据库只读访问与层级查询
