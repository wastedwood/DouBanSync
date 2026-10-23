<p align="center"><img src="app/static/img/brand-mark.svg" alt="DouBanSync" width="68"></p>
<h1 align="center">DouBanSync</h1>
<p align="center">把飞牛影视的观看记录自动同步到豆瓣。</p>

---

- 电影看完，标记为「看过」
- 剧集按季同步：开始看标记「在看」，看完最后一集标记「看过」
- 只读访问飞牛数据库，不做任何修改
- 可选 Bark 推送同步结果和 Cookie 过期提醒

## 部署

1. 创建 `docker-compose.yml`：

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
   ```

2. 启动：`docker compose up -d`

3. 打开 `http://<NAS_IP>:58080/config`，选择飞牛用户，粘贴豆瓣 Cookie（页面内有获取方法），保存后点「立即同步」。

升级：`docker compose pull && docker compose up -d`

## 说明

- 电影播放进度达到 90% 记为看过，有进度但未达到记为在看；剧集看完该季最后一集才记为看过，否则为在看。阈值可在配置页修改。
- 最后一集按刮削到的该季总集数计算，追更中的季不会提前记为看过。
- 多季剧集每季对应豆瓣上的独立条目。匹配不到的季会记为失败，不会误标到第一季，可在「同步日志」查看后到豆瓣手动标记。
- 特别篇不同步。
- 配置页可开启「移除豆瓣想看中飞牛库已有的影片」（默认关闭），同步时会把已入库影片的想看标记去掉。
- Cookie 过期后重新获取并保存即可。

## 开发

```bash
pip install -r requirements.txt
python -m pytest -q
python -m app   # http://localhost:5000
```

## 致谢

- [MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching)
- [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)
