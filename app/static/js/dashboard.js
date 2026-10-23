(() => {
    const button = document.getElementById('btn-sync');
    const status = document.getElementById('sync-status');
    const livePanel = document.getElementById('sync-live-log');
    const logContainer = document.getElementById('log-container');
    const logCountElement = document.getElementById('log-count');
    if (!status || !livePanel || !logContainer) return;

    const labels = {
        info: '提示', mark_done: '已标记看过', mark_doing: '已标记在看', remove_wish: '已移出想看',
        skip_threshold: '播放进度不足', skip_middle: '中间集跳过', skip_done: '已同步',
        error_search: '搜索失败', error_api: '豆瓣接口失败', auth_failed: 'Cookie 失效',
        no_new_records: '没有新记录', all_filtered: '没有符合条件的记录', no_change_skip: '播放记录无变化'
    };
    let eventSource = null;
    let logCount = 0;

    const resetLog = () => {
        livePanel.hidden = false;
        logContainer.replaceChildren();
        logCount = 0;
        if (logCountElement) logCountElement.textContent = '0 条';
    };

    const appendText = (parent, className, text) => {
        const span = document.createElement('span');
        span.className = className;
        span.textContent = text;
        parent.appendChild(span);
    };

    const addLog = (action, title, detail) => {
        logCount += 1;
        if (logCountElement) logCountElement.textContent = `${logCount} 条`;
        const line = document.createElement('div');
        const time = new Date().toLocaleTimeString('zh-CN', {hour12: false});
        const tone = ['info', 'no_new_records', 'all_filtered', 'no_change_skip'].includes(action) ? 'info' : action;
        appendText(line, 'log-time', `[${time}] `);
        appendText(line, `log-${tone}`, labels[action] || action || '提示');
        if (title) appendText(line, '', ` ${title}`);
        if (detail) appendText(line, 'text-secondary', ` — ${detail}`);
        logContainer.appendChild(line);
        logContainer.scrollTop = logContainer.scrollHeight;
    };

    const connect = () => {
        eventSource?.close();
        eventSource = new EventSource('/api/sync/stream');
        eventSource.onmessage = (event) => {
            let data;
            try { data = JSON.parse(event.data); } catch { return; }
            if (data.type === 'connected') return;
            if (data.type === 'log') addLog(data.action, data.series_title, data.detail);
            if (data.type === 'sync_start') {
                resetLog();
                addLog('info', '同步开始', '');
                status.textContent = '正在读取新增记录…';
            }
            if (data.type === 'sync_end') {
                addLog('info', '同步完成', data.success ? '' : '任务执行失败');
                if (button) button.disabled = false;
                status.textContent = data.success ? '同步完成，正在刷新页面…' : '同步失败，请查看上方记录';
                if (data.success) window.setTimeout(() => window.location.reload(), 1600);
            }
        };
    };

    button?.addEventListener('click', async () => {
        button.disabled = true;
        status.textContent = '正在启动同步…';
        resetLog();
        try {
            const response = await fetch('/api/sync/run', {method: 'POST'});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '无法启动同步');
        } catch (error) {
            status.textContent = error.message;
            button.disabled = false;
        }
    });

    connect();
})();
