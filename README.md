<p align="center"><img src="app/static/img/brand-mark.svg" alt="DouBanSync" width="68"></p>
<h1 align="center">DouBanSync</h1>
<p align="center">在飞牛影视看完，豆瓣自动帮你点「看过」 🎬</p>

---

- 🎞️ 电影看完 → **看过**
- 📺 剧集按季同步：开始看 → **在看**，看完最后一集 → **看过**
- 🔒 只读飞牛数据库，不碰你的数据
- 🔔 可选 Bark 推送，同步结果和 Cookie 过期都会提醒

## 三步跑起来

**① 写一个 `docker-compose.yml`**

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

**② 启动**

```bash
docker compose up -d
```

**③ 打开 `http://<NAS_IP>:58080/config`**，选飞牛用户、粘贴豆瓣 Cookie（页面里有图文教程），保存后点「立即同步」。完事 ✨

想升级？`docker compose pull && docker compose up -d`

## 小贴士

- **只看了几分钟的不会同步**：默认播放到 90% 才算，可在配置页调整
- **多季剧每季单独标记**：对不上豆瓣的季宁可跳过，不会误标到第一季，在「同步日志」里能看到，去豆瓣手动点一下就好
- **特别篇不同步**
- **Cookie 过期了**：重新复制一份粘贴保存即可

## 开发

```bash
pip install -r requirements.txt
python -m pytest -q
python -m app   # http://localhost:5000
```

## 致谢

[MoviePilot-Plugins/doubanwatching](https://github.com/honue/MoviePilot-Plugins/tree/main/plugins/doubanwatching) · [fntv-record-view](https://github.com/QiaoKes/fntv-record-view)
