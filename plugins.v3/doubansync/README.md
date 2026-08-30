# DouBanSync MoviePilot V3 插件

这个目录是 DouBanSync 的 MoviePilot V3 插件版本。它保留原项目的同步规则：

- 读取飞牛影视 trimmedia.db，数据库只读，并通过临时副本避免锁竞争。
- 播放完成度低于阈值时跳过。
- 电影同步为豆瓣「看过」。
- 剧集首集/进行中同步为「在看」，末集同步为「看过」，中间集不重复调用豆瓣。
- 自动识别标准季度层级与多候选智能季度匹配；缺少季度层级时按集号回退推断季度。
- 同步状态和日志存放在 MoviePilot 分配的插件数据目录，不写入 FNTV 数据库。

## 安装

1. 把本仓库加入 MoviePilot 的插件市场仓库配置，或从仓库中安装 DouBanSync。
2. 在插件配置中填写 MoviePilot 容器内的 FNTV 数据库路径。
3. 粘贴豆瓣 Cookie，选择 FNTV 用户，保存配置。
4. 开启插件；可以使用“保存后立即同步一次”或详情页的“立即同步”按钮测试。

如果使用 Docker，必须把 FNTV 数据库以只读方式挂载到 MoviePilot 容器，例如：

    - /宿主机路径/trimmedia.db:/fntv-db/trimmedia.db:ro

此时插件内填写：

    /fntv-db/trimmedia.db

## 调度

- 间隔模式：按配置的小时数执行，范围 1 到 168 小时。
- Cron 模式：使用五段式表达式，例如 0 3 * * *。
- MoviePilot 公共调度器负责注册和撤销任务，插件不会额外启动一个常驻 APScheduler。

## Cookie

Cookie 仅用于当前插件配置和豆瓣请求，不写入 Git。Cookie 过期时同步会失败，并可通过 Bark Key 接收提醒。

## 兼容边界

这是 MoviePilot V3 专用目录，索引要求 MoviePilot >=3.0.0。原项目根目录下的 Flask/Docker 入口仍可独立运行。
