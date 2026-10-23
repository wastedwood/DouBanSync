<p align="center"><img src="app/static/img/brand-mark.svg" alt="DouBanSync" width="68"></p>
<h1 align="center">DouBanSync</h1>
<p align="center">把飞牛影视的观看记录自动同步到豆瓣，标记「在看」和「看过」。</p>

---

## 它做什么

定时读取飞牛影视（FNTV）数据库中的播放记录，在豆瓣找到对应条目并标记状态：

- **电影**：看完 → 看过
- **剧集**：按季同步，开始看 → 在看，看完最后一集 → 看过
- 飞牛数据库只读访问，不会被修改；只同步你在配置页选择的那一个飞牛用户

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
      # 飞牛数据库（只读）。路径不同时只改冒号左侧
      - /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro
      # 同步状态与配置
      - ./sync_state:/app/sync_state
    environment:
      - TZ=Asia/Shanghai
```

### 2. 启动

```bash
docker compose up -d
```

### 3. 配置

打开 `http://<NAS_IP>:58080/config`：

1. **FNTV 数据库**：保持默认路径，点「测试连接」，然后选择要同步的飞牛用户
2. **豆瓣 Cookie**：粘贴后点「验证 Cookie」。获取方法见页面内的图文指南，简单说就是：电脑浏览器登录豆瓣 → F12 → Network → 刷新 → 复制请求头里的 `Cookie`
3. **同步计划、播放阈值、Bark 推送**：按需调整，见下方配置项
4. 保存，回到首页点「立即同步」完成首次同步

### 更新

```bash
docker compose pull && docker compose up -d
```

## 同步规则

| 类型 | 条件 | 豆瓣状态 |
|------|------|----------|
| 电影 | 飞牛标记已看，或播放进度 ≥ 阈值 | 看过 |
| 剧集·开始看 | 该季首次同步且未看完 | 在看 |
| 剧集·看到中间 | 进度推进 | 不请求豆瓣，只记录进度 |
| 剧集·看完 | 看到该季最后一集（或首次同步时已看完） | 看过 |

**多季剧集**：每季对应豆瓣上的独立条目，第 2 季及以后会搜索「剧名 第N季」，季度和剧名都对得上才标记。找不到时记为同步失败，不会误标到第一季，需在豆瓣手动标记。

**不同步的内容**：第 0 季（特别篇）、播放进度低于阈值的记录、已标记看过的条目。

## 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| FNTV 数据库路径 | 容器内路径，可用环境变量 `FNTV_DB_PATH` 覆盖 | `/fntv-db/trimmedia.db` |
| 同步用户 | 只同步该飞牛用户的记录 | — |
| 豆瓣 Cookie | 需包含 `dbcl2` 和 `ck` | — |
| 同步计划 | 间隔模式（每 N 小时，1–168）或 Cron 表达式 | 每 24 小时 |
| 播放阈值 | 播放进度达到该百分比才同步，0 为不限制 | 90% |
| 仅自己可见 | 豆瓣标记是否私密 | 是 |
| Bark Key | iOS Bark 推送，同步结果与 Cookie 过期提醒；留空不推送 | 空 |

## 常见问题

- **Cookie 过期**：同步会失败，配置了 Bark 会收到提醒。按同样方法重新获取并保存即可。
- **某部剧搜索失败**：豆瓣条目名与飞牛剧名差异较大时会搜不到。例如续作在豆瓣叫「马大帅2」而不是「马大帅 第二季」。在「同步日志」页查看失败项，到豆瓣手动标记。
- **部分旧记录没有同步**：飞牛重新刮削后可能残留找不到所属剧集的单集记录，这类记录会被跳过。

## 本地开发

```bash
pip install -r requirements.txt
python -m pytest -q    # 运行测试
python -m app          # 启动开发服务器，http://localhost:5000
```

运行时数据写在 `sync_state/`，可用环境变量 `SYNC_STATE_DIR` 指定其他目录。

## 致谢

- [MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)
- [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)
