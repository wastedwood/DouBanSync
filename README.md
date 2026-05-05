# 飞牛观影同步 · FNTV → Douban Sync

将飞牛影视（FNTV）的观看记录自动同步到豆瓣书影音档案。

## 功能

- **自动同步** — 定时读取飞牛影视 SQLite 数据库，通过豆瓣内部 API 标记观影状态
- **智能跨季匹配** — 自动识别飞牛扁平结构中的季度边界，正确匹配豆瓣分季条目
- **播放阈值过滤** — 设置播放百分比门槛，避免点开就标记的误报
- **实时日志** — 浏览器端 SSE 流式展示同步过程，每步操作实时可见

## 同步规则

- **电影**：观看后自动标记"看过"
- **电视剧**：首集标记"在看"，末集标记"看过"，中间集跳过
- **智能季推断**：当飞牛缺少季度层级时，从剧集编号分布自动推断季度边界
- **播放阈值**：低于设定百分比（默认 90%）的播放记录自动跳过

## 部署

### 前提

- Docker + Docker Compose
- 飞牛影视已正常运行
- 豆瓣 Cookie（从浏览器提取）

### 步骤

1. 将项目文件（`app/`、`Dockerfile`、`docker-compose.yml`、`requirements.txt`、`config.yaml`、`.dockerignore`）放到部署目录，编辑 `docker-compose.yml`，修改 volumes 中的数据库路径

```yaml
volumes:
  # 飞牛影视数据库文件（只读），根据实际路径修改
  - /vol1/@apps/trimmedia/trimmedia.db:/fntv-db/trimmedia.db:ro
  # 持久化同步状态
  - ./sync_state:/app/sync_state
```

> 飞牛影视数据库通常位于飞牛 OS 的 `/usr/local/apps/@appdata/trim.media/database/trimmedia.db`，`/vol1/@apps/trimmedia/trimmedia.db` 是其符号链接

2. 构建并启动容器：

```bash
docker compose up -d --build
```

3. 打开 `http://<你的IP>:58080` 进入配置页
4. 填写：
   - FNTV 数据库路径（容器内路径：`/fntv-db/trimmedia.db`，挂载正确则无需修改）
   - 豆瓣 Cookie（见下方指南）
   - 选择同步用户
5. 点击"保存配置"，返回状态页点击"立即同步"——实时日志面板会同步显示进度

### 获取豆瓣 Cookie

1. 浏览器打开 https://movie.douban.com/ 并登录
2. 按 F12 打开开发者工具 → Network 标签
3. 刷新页面，找到第一个 `movie.douban.com` 的 document 请求
4. 在 Request Headers 中找到 `Cookie:` 行，右键 Copy Value
5. 粘贴到配置页的 Cookie 输入框

## 配置项

| 配置 | 说明 |
|------|------|
| FNTV 数据库路径 | 容器内数据库路径，默认 `/fntv-db/trimmedia.db` |
| 同步用户 | 选择要同步哪位飞牛用户的观看记录 |
| 豆瓣 Cookie | 浏览器提取的完整 Cookie 字符串 |
| 同步间隔 | 默认 24 小时，可 1~168 小时 |
| 播放阈值 | 超过此百分比才算已看（默认 90%，0 为不限制） |
| 仅自己可见 | 豆瓣标记是否仅自己可见 |

## 开发

```bash
pip install -r requirements.txt
python -m app
```

访问 http://localhost:5000
