(() => {
    const form = document.getElementById('config-form');
    if (!form) return;

    const byId = (id) => document.getElementById(id);
    const intervalPanel = byId('interval-config');
    const cronPanel = byId('cron-config');
    const cronExpression = byId('cron_expr');
    const cronDisplay = byId('cron-expr-display');
    const cronPreview = byId('cron-preview-text');
    const scheduleSummary = byId('schedule-summary');

    const setStatus = (element, message, tone = 'secondary') => {
        element.textContent = message;
        element.className = `field-status text-${tone}`;
    };

    const setButtonBusy = (button, busy, busyText) => {
        if (!button.dataset.label) button.dataset.label = button.textContent;
        button.disabled = busy;
        button.textContent = busy ? busyText : button.dataset.label;
    };

    const populate = (select, start, end, suffix = '', pad = true) => {
        for (let value = start; value <= end; value += 1) {
            const option = document.createElement('option');
            option.value = String(value);
            option.textContent = `${pad ? String(value).padStart(2, '0') : value}${suffix}`;
            select.appendChild(option);
        }
    };
    populate(byId('cron_hour'), 0, 23);
    populate(byId('cron_minute'), 0, 59);
    populate(byId('cron_dom'), 1, 31, '日', false);
    populate(byId('cron_month'), 1, 12, '月', false);

    const describeCron = (expression) => {
        const parts = expression.trim().split(/\s+/);
        if (parts.length !== 5) return '表达式格式不正确';
        const [minute, hour, day, month, weekday] = parts;
        if (!/^\d+$/.test(minute) || !/^\d+$/.test(hour)) return '已使用高级计划';
        const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
        if (day === '*' && month === '*' && weekday === '*') return `每天 ${time}`;
        if (day === '*' && month === '*' && /^[\d,]+$/.test(weekday)) {
            const names = {0: '日', 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '日'};
            return `${weekday.split(',').map((item) => `周${names[item] ?? item}`).join('、')} ${time}`;
        }
        if (/^\d+$/.test(day) && month === '*' && weekday === '*') return `每月 ${day} 日 ${time}`;
        if (/^\d+$/.test(day) && /^\d+$/.test(month) && weekday === '*') return `每年 ${month} 月 ${day} 日 ${time}`;
        return '已使用高级计划';
    };

    const commitCron = (expression) => {
        if (!expression) return;
        cronExpression.value = expression;
        cronDisplay.textContent = expression;
        cronPreview.textContent = describeCron(expression);
        scheduleSummary.textContent = describeCron(expression);
    };

    const showCronControls = () => {
        const frequency = byId('cron_freq').value;
        byId('cron_time_group').hidden = frequency === 'custom';
        byId('cron_dow_group').hidden = frequency !== 'weekly';
        byId('cron_dom_group').hidden = !['monthly', 'yearly'].includes(frequency);
        byId('cron_month_group').hidden = frequency !== 'yearly';
        byId('cron_custom_group').hidden = frequency !== 'custom';
    };

    const generateCron = () => {
        const frequency = byId('cron_freq').value;
        const hour = byId('cron_hour').value;
        const minute = byId('cron_minute').value;
        let expression = '';
        if (frequency === 'daily') expression = `${minute} ${hour} * * *`;
        if (frequency === 'weekly') {
            const days = [...document.querySelectorAll('#cron_dow_group input:checked')].map((input) => input.value).sort((a, b) => Number(a) - Number(b));
            if (days.length) expression = `${minute} ${hour} * * ${days.join(',')}`;
        }
        if (frequency === 'monthly') expression = `${minute} ${hour} ${byId('cron_dom').value} * *`;
        if (frequency === 'yearly') expression = `${minute} ${hour} ${byId('cron_dom').value} ${byId('cron_month').value} *`;
        if (frequency === 'custom') expression = byId('cron_raw').value.trim();
        commitCron(expression);
    };

    const applyCron = (expression) => {
        const parts = expression.trim().split(/\s+/);
        if (parts.length !== 5) return;
        const [minute, hour, day, month, weekday] = parts;
        byId('cron_hour').value = String(Number(hour));
        byId('cron_minute').value = String(Number(minute));
        document.querySelectorAll('#cron_dow_group input').forEach((input) => { input.checked = false; });
        if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && weekday !== '*') {
            byId('cron_freq').value = 'weekly';
            weekday.split(',').forEach((value) => {
                const input = document.querySelector(`#cron_dow_group input[value="${CSS.escape(value)}"]`);
                if (input) input.checked = true;
            });
        } else if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day !== '*' && month !== '*') {
            byId('cron_freq').value = 'yearly';
            byId('cron_dom').value = day;
            byId('cron_month').value = month;
        } else if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day !== '*') {
            byId('cron_freq').value = 'monthly';
            byId('cron_dom').value = day;
        } else if (/^\d+$/.test(minute) && /^\d+$/.test(hour)) {
            byId('cron_freq').value = 'daily';
        } else {
            byId('cron_freq').value = 'custom';
            byId('cron_raw').value = expression;
        }
        showCronControls();
        commitCron(expression);
    };

    const switchMode = () => {
        const cronMode = document.querySelector('input[name="sync_mode"]:checked')?.value === 'cron';
        intervalPanel.hidden = cronMode;
        cronPanel.hidden = !cronMode;
        if (cronMode) commitCron(cronExpression.value || '0 3 * * *');
        else scheduleSummary.textContent = `每 ${byId('sync_interval_hours').value || 24} 小时`;
    };

    document.querySelectorAll('input[name="sync_mode"]').forEach((radio) => radio.addEventListener('change', switchMode));
    byId('sync_interval_hours').addEventListener('input', switchMode);
    byId('cron_freq').addEventListener('change', () => { showCronControls(); generateCron(); });
    ['cron_hour', 'cron_minute', 'cron_dom', 'cron_month'].forEach((id) => byId(id).addEventListener('change', generateCron));
    byId('cron_dow_group').addEventListener('change', generateCron);
    byId('cron_raw').addEventListener('input', generateCron);
    document.querySelectorAll('[data-cron]').forEach((button) => button.addEventListener('click', () => {
        byId('mode_cron').checked = true;
        switchMode();
        applyCron(button.dataset.cron);
    }));

    byId('btn-test-db').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        const status = byId('db-status');
        const path = byId('fntv_db_path').value.trim();
        if (!path) { setStatus(status, '请先填写数据库路径', 'danger'); return; }
        setButtonBusy(button, true, '测试中…');
        setStatus(status, '正在检查数据库…');
        try {
            const response = await fetch('/api/fntv/test-db', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({db_path: path})});
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || '连接失败');
            setStatus(status, '连接成功，用户列表已刷新', 'success');
            const userResponse = await fetch(`/api/fntv/users?db_path=${encodeURIComponent(path)}`);
            const userData = await userResponse.json();
            if (!userResponse.ok) throw new Error(userData.error || '读取用户失败');
            const select = byId('selected_user');
            const current = select.value;
            select.replaceChildren(new Option('请选择用户', ''));
            userData.users.forEach((user) => select.add(new Option(user.username, user.guid, false, user.guid === current)));
        } catch (error) {
            setStatus(status, error.message, 'danger');
        } finally {
            setButtonBusy(button, false, '');
        }
    });

    byId('btn-test-cookie').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        const status = byId('cookie-status');
        const cookie = byId('douban_cookie').value.trim();
        if (!cookie) { setStatus(status, '请先粘贴 Cookie', 'danger'); return; }
        setButtonBusy(button, true, '验证中…');
        setStatus(status, '正在连接豆瓣…');
        try {
            const response = await fetch('/api/douban/check-cookie', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cookie})});
            const data = await response.json();
            if (!data.ok) throw new Error(data.message || 'Cookie 无效或已过期');
            setStatus(status, 'Cookie 有效，可以正常同步', 'success');
        } catch (error) {
            setStatus(status, error.message, 'danger');
        } finally {
            setButtonBusy(button, false, '');
        }
    });

    byId('btn-test-bark').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        const status = byId('bark-status');
        const key = byId('bark_key').value.trim();
        if (!key) { setStatus(status, '请先填写 Bark Device Key', 'danger'); return; }
        setButtonBusy(button, true, '发送中…');
        setStatus(status, '正在发送测试通知…');
        try {
            const response = await fetch('/api/bark/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({device_key: key})});
            const data = await response.json();
            if (!data.ok) throw new Error(data.message || '发送失败');
            setStatus(status, '通知已发送，请查看手机', 'success');
        } catch (error) {
            setStatus(status, error.message, 'danger');
        } finally {
            setButtonBusy(button, false, '');
        }
    });

    applyCron(form.dataset.currentCron || '0 3 * * *');
    switchMode();
})();
