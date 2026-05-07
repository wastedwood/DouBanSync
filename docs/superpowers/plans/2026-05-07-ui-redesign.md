# DouBanSync UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all frontend templates with sidebar nav, custom CSS theme, card-based layout, and mobile responsiveness.

**Architecture:** Pure CSS custom properties in a single `style.css`, sidebar layout in `base.html` replacing top navbar, each page template gets focused markup updates without functional changes. No build step, no JS framework.

**Tech Stack:** Bootstrap 5.3, Jinja2, vanilla CSS with custom properties, Unicode/Emoji icons

---

### Task 1: Create global stylesheet (`static/style.css`)

**Files:**
- Create: `app/static/style.css`

This is the core of the redesign. All CSS custom properties, layout, card, sidebar, and component styles live here.

- [ ] **Step 1: Create `app/static/style.css` with CSS variables and base layout**

```css
/* ============================================
   DouBanSync — Custom Theme
   ============================================ */

:root {
  /* Brand */
  --color-sidebar: #0f172a;
  --color-sidebar-hover: #1e293b;
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-bg: #f8fafc;
  --color-card: #ffffff;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #94a3b8;
  --color-border: #e2e8f0;
  --color-border-light: #f1f5f9;

  /* Semantic */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-info: #22d3ee;

  /* Geometry */
  --radius-card: 10px;
  --radius-btn: 8px;
  --radius-input: 6px;
  --radius-badge: 10px;
  --shadow-card: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-card-hover: 0 4px 12px rgba(0,0,0,0.08);

  /* Sidebar */
  --sidebar-width: 200px;
  --sidebar-collapsed: 56px;
}

/* ── Base ─────────────────────────────────── */
body {
  background: var(--color-bg);
  font-size: .9rem;
  overflow-x: hidden;
}

/* ── Sidebar ──────────────────────────────── */
.sidebar {
  position: fixed;
  top: 0; left: 0;
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--color-sidebar);
  display: flex;
  flex-direction: column;
  z-index: 1030;
  transition: width .2s ease;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 20px;
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
}

.sidebar-logo-icon {
  width: 28px; height: 28px;
  background: var(--color-primary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.sidebar-nav {
  flex: 1;
  padding: 4px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 13px;
  transition: all .15s ease;
  white-space: nowrap;
}

.sidebar-link:hover {
  background: rgba(255,255,255,.06);
  color: #e2e8f0;
}

.sidebar-link.active {
  background: rgba(59,130,246,.15);
  color: #60a5fa;
}

.sidebar-footer {
  padding: 14px 16px;
  border-top: 1px solid var(--color-sidebar-hover);
  color: #475569;
  font-size: 11px;
}

/* ── Sidebar collapse toggle (mobile) ─────── */
.sidebar-toggle {
  display: none;
  position: fixed;
  top: 10px; left: 10px;
  z-index: 1040;
  background: var(--color-sidebar);
  color: #fff;
  border: none;
  border-radius: 8px;
  width: 40px; height: 40px;
  font-size: 20px;
  cursor: pointer;
  align-items: center;
  justify-content: center;
}

.sidebar-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.4);
  z-index: 1025;
}

/* ── Main Content ─────────────────────────── */
.main-content {
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  padding: 20px 24px 40px;
  transition: margin-left .2s ease;
}

/* ── Breadcrumb ───────────────────────────── */
.breadcrumb-custom {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 16px;
}

.breadcrumb-custom a {
  color: var(--color-text-muted);
  text-decoration: none;
}

.breadcrumb-custom a:hover {
  color: var(--color-primary);
}

.breadcrumb-custom .current {
  color: var(--color-text-secondary);
}

/* ── Cards ────────────────────────────────── */
.card-custom {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  transition: box-shadow .2s ease, transform .2s ease;
}

.card-custom:hover {
  box-shadow: var(--shadow-card-hover);
}

.card-header-custom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
  user-select: none;
}

.card-header-custom:first-child {
  border-radius: var(--radius-card) var(--radius-card) 0 0;
}

.card-body-custom {
  padding: 16px;
}

/* ── Status cards (dashboard) ─────────────── */
.stat-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 16px 20px;
  box-shadow: var(--shadow-card);
  transition: box-shadow .2s ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-card-hover);
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: .03em;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
}

.stat-value.text-success { color: var(--color-success); }
.stat-value.text-danger  { color: var(--color-danger); }
.stat-value.text-warning { color: var(--color-warning); }

.stat-number-lg {
  font-size: 1.75rem;
  font-weight: 700;
}

/* ── Badges ───────────────────────────────── */
.badge-custom {
  font-size: 10px;
  padding: 2px 10px;
  border-radius: var(--radius-badge);
  font-weight: 500;
}

/* ── Tables ───────────────────────────────── */
.table-custom {
  margin-bottom: 0;
}

.table-custom thead th {
  background: #f8fafc;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
  padding: 10px 16px;
}

.table-custom td {
  padding: 10px 16px;
  font-size: 13px;
  vertical-align: middle;
}

/* ── Sync terminal log ────────────────────── */
.log-terminal {
  max-height: 360px;
  overflow-y: auto;
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: .82rem;
  line-height: 1.6;
  background: #1a1d23;
  color: #e0e0e0;
  border-radius: var(--radius-input);
}

.log-terminal div {
  padding: 0 6px;
  white-space: nowrap;
}

.log-terminal .log-time { color: #6b7280; }
.log-terminal .log-mark_done    { color: #34d399; }
.log-terminal .log-mark_doing   { color: #60a5fa; }
.log-terminal .log-skip_threshold { color: #fbbf24; }
.log-terminal .log-skip_middle  { color: #fbbf24; }
.log-terminal .log-skip_done    { color: #6b7280; }
.log-terminal .log-error_search { color: #f87171; }
.log-terminal .log-error_api    { color: #f87171; }
.log-terminal .log-auth_failed  { color: #f87171; }
.log-terminal .log-info         { color: #22d3ee; }

/* ── Form tweaks ──────────────────────────── */
.form-control, .form-select {
  border-color: var(--color-border);
  font-size: .875rem;
  border-radius: var(--radius-input);
}

.form-control:focus, .form-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59,130,246,.15);
}

/* ── Buttons ──────────────────────────────── */
.btn {
  border-radius: var(--radius-btn);
  font-size: .875rem;
  transition: all .15s ease;
}

.btn:hover {
  transform: translateY(-1px);
}

.btn-primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.btn-primary:hover {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

/* ── Page heading ─────────────────────────── */
.page-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 16px;
}

/* ── Accordion card group (config page) ───── */
.accordion-custom .card-custom {
  margin-bottom: 10px;
}

.accordion-custom .card-custom:last-child {
  margin-bottom: 0;
}

.accordion-custom .card-body-custom {
  display: none;
}

.accordion-custom .card-body-custom.open {
  display: block;
}

.accordion-custom .card-header-custom .arrow {
  transition: transform .2s ease;
  font-size: 12px;
  color: var(--color-text-muted);
}

.accordion-custom .card-header-custom .arrow.open {
  transform: rotate(180deg);
}

/* ── Status dot ───────────────────────────── */
.status-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.status-dot.connected { background: var(--color-success); }
.status-dot.disconnected { background: var(--color-danger); }
.status-dot.pending { background: var(--color-warning); }

/* ── Collapse toggle ──────────────────────── */
.collapse-icon {
  transition: transform .2s ease;
}

.collapse-icon.open {
  transform: rotate(180deg);
}

/* ── Empty state ──────────────────────────── */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-text-muted);
}

.empty-state .empty-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
}

/* ── Alert tweaks ─────────────────────────── */
.alert-custom {
  border-radius: var(--radius-card);
  border: none;
}

/* ── Pagination tweaks ────────────────────── */
.pagination-custom .page-link {
  border-radius: 6px;
  margin: 0 2px;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: 6px 14px;
}

.pagination-custom .page-link:hover {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.pagination-custom .page-item.disabled .page-link {
  opacity: .5;
  pointer-events: none;
}

/* ── Responsive ───────────────────────────── */
@media (max-width: 768px) {
  .sidebar {
    width: var(--sidebar-collapsed);
  }

  .sidebar .sidebar-logo span,
  .sidebar .sidebar-link span:not(.nav-icon),
  .sidebar .sidebar-footer {
    display: none;
  }

  .sidebar.open {
    width: var(--sidebar-width);
  }

  .sidebar.open .sidebar-logo span,
  .sidebar.open .sidebar-link span:not(.nav-icon),
  .sidebar.open .sidebar-footer {
    display: inline;
  }

  .sidebar-toggle {
    display: flex;
  }

  .main-content {
    margin-left: var(--sidebar-collapsed);
    padding: 60px 12px 24px;
  }

  .main-content.shifted {
    margin-left: var(--sidebar-width);
  }

  .sidebar-backdrop.active {
    display: block;
  }

  .stat-card {
    padding: 12px 14px;
  }

  .stat-number-lg {
    font-size: 1.3rem;
  }
}
```

- [ ] **Step 2: Create directory and verify**

Run: `mkdir -Force app/static`
Expected: directory created (or already exists)

```powershell
ls app/static
```
Expected: shows style.css

- [ ] **Step 3: Commit**

```powershell
git add app/static/style.css
git commit -m "style: add global CSS theme with sidebar layout, cards, and responsive styles"
```

---

### Task 2: Refactor base.html — sidebar layout

**Files:**
- Modify: `app/templates/base.html`

Replace the top navbar with sidebar navigation. Add breadcrumb block. Link to new style.css.

- [ ] **Step 1: Rewrite `base.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}飞牛观影同步{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='style.css') }}" rel="stylesheet">
    {% block head %}{% endblock %}
</head>
<body>

<!-- Sidebar -->
<button class="sidebar-toggle" id="sidebarToggle" onclick="toggleSidebar()">☰</button>
<div class="sidebar-backdrop" id="sidebarBackdrop" onclick="toggleSidebar()"></div>

<nav class="sidebar" id="sidebar">
    <div class="sidebar-logo">
        <div class="sidebar-logo-icon">D</div>
        <span>DouBanSync</span>
    </div>
    <div class="sidebar-nav">
        {% set nav_items = [
            ('/', '📊', '状态面板'),
            ('/config', '⚙️', '配置'),
            ('/history', '📋', '同步日志'),
        ] %}
        {% for href, icon, label in nav_items %}
        <a href="{{ href }}" class="sidebar-link{% if request.path == href %} active{% endif %}">
            <span>{{ icon }}</span>
            <span>{{ label }}</span>
        </a>
        {% endfor %}
    </div>
    <div class="sidebar-footer">v1.0.0</div>
</nav>

<!-- Main -->
<div class="main-content" id="mainContent">
    <div class="breadcrumb-custom">
        {% block breadcrumb %}{% endblock %}
    </div>
    {% block content %}{% endblock %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebarBackdrop').classList.toggle('active');
}
</script>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Commit**

```powershell
git add app/templates/base.html
git commit -m "refactor: replace top navbar with sidebar layout in base.html"
```

---

### Task 3: Update dashboard.html

**Files:**
- Modify: `app/templates/dashboard.html`

Update to use new CSS classes. Add breadcrumb, use stat-card class, clean up inline styles. Keep SSE log terminal intact.

- [ ] **Step 1: Rewrite `dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}状态面板 - 飞牛观影同步{% endblock %}
{% block breadcrumb %}<a href="/">首页</a> / <span class="current">状态面板</span>{% endblock %}

{% block content %}
<h1 class="page-title">状态面板</h1>

<!-- Status cards row -->
<div class="row g-3 mb-4">
    <div class="col-6 col-md-3">
        <div class="stat-card h-100">
            <div class="stat-label">数据库</div>
            <div class="stat-value {% if db_connected %}text-success{% else %}text-danger{% endif %}">
                {% if db_connected %}已连接{% else %}未连接{% endif %}
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="stat-card h-100">
            <div class="stat-label">豆瓣 Cookie</div>
            <div class="stat-value {% if cookie_set %}text-success{% else %}text-danger{% endif %}">
                {% if cookie_set %}已设置{% else %}未设置{% endif %}
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="stat-card h-100">
            <div class="stat-label">同步用户</div>
            <div class="stat-value {% if user_set %}text-success{% else %}text-warning{% endif %}">
                {% if user_set %}已选择{% else %}未选择{% endif %}
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="stat-card h-100">
            <div class="stat-label">最后同步</div>
            <div class="stat-value" style="font-size:1rem;">{{ last_sync or '从未' }}</div>
        </div>
    </div>
</div>

<!-- Stats row -->
<div class="row g-3 mb-4">
    <div class="col-md-4">
        <div class="stat-card text-center">
            <div class="stat-label">同步总数</div>
            <div class="stat-number-lg">{{ stats.total }}</div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="stat-card text-center">
            <div class="stat-label">已完成</div>
            <div class="stat-number-lg text-success">{{ stats.done }}</div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="stat-card text-center">
            <div class="stat-label">失败</div>
            <div class="stat-number-lg text-danger">{{ stats.failed }}</div>
        </div>
    </div>
</div>

<!-- Sync controls -->
<div class="card-custom p-3 mb-4">
    <div class="d-flex align-items-center gap-3">
        <button class="btn btn-primary" id="btn-sync" {% if not user_set or not cookie_set %}disabled{% endif %}>
            立即同步
        </button>
        <span class="text-muted small" id="sync-status"></span>
    </div>

    <!-- SSE log terminal -->
    <div id="sync-live-log" class="mt-3" style="display:none;">
        <hr class="my-2">
        <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="small fw-semibold text-muted">同步日志（实时）</span>
            <span class="small text-muted" id="log-count">0 条</span>
        </div>
        <div class="log-terminal p-2" id="log-container"></div>
    </div>
</div>

<!-- Config warning -->
{% if not user_set or not cookie_set or not db_connected %}
<div class="alert alert-warning alert-custom">
    <strong>配置未完成</strong>
    <ul class="mb-0 mt-1">
        {% if not db_connected %}<li>FNTV 数据库未连接，请前往<a href="/config" class="alert-link">配置页</a>设置数据库路径</li>{% endif %}
        {% if not cookie_set %}<li>豆瓣 Cookie 未设置，请前往<a href="/config" class="alert-link">配置页</a>填入 Cookie</li>{% endif %}
        {% if not user_set %}<li>未选择同步用户，请前往<a href="/config" class="alert-link">配置页</a>选择用户</li>{% endif %}
    </ul>
</div>
{% endif %}
{% endblock %}

{% block scripts %}
<script>
let syncEventSource = null;
let logCount = 0;
const logContainer = document.getElementById('log-container');
const syncLiveLog = document.getElementById('sync-live-log');
const logCountEl = document.getElementById('log-count');

function connectSSE() {
    if (syncEventSource) syncEventSource.close();
    syncEventSource = new EventSource('/api/sync/stream');
    syncEventSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'connected') return;
            if (data.type === 'log') {
                addLogEntry(data.action, data.series_title, data.detail);
            } else if (data.type === 'sync_start') {
                syncLiveLog.style.display = 'block';
                logContainer.innerHTML = '';
                logCount = 0;
                if (logCountEl) logCountEl.textContent = '0 条';
                addLogEntry('info', '同步开始', '');
            } else if (data.type === 'sync_complete') {
                addLogEntry('info', '同步完成', data.success ? '' : '失败');
                const btn = document.getElementById('btn-sync');
                if (btn) btn.disabled = false;
                document.getElementById('sync-status').textContent = '同步完成';
                setTimeout(() => location.reload(), 2000);
            }
        } catch(e) {}
    };
}

function addLogEntry(action, title, detail) {
    if (!logContainer) return;
    logCount++;
    if (logCountEl) logCountEl.textContent = logCount + ' 条';
    const line = document.createElement('div');
    const time = new Date().toLocaleTimeString('zh-CN', {hour12: false});
    const actionClass = 'log-' + (action === 'info' || action === 'no_new_records' || action === 'all_filtered' ? 'info' : action);
    line.innerHTML = '<span class="log-time">[' + time + ']</span> <span class="' + actionClass + '">' + escapeHtml(action) + '</span> ' + escapeHtml(title || '') + (detail ? ' <span style="color:#9ca3af;">— ' + escapeHtml(detail) + '</span>' : '');
    logContainer.appendChild(line);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', function() {
    connectSSE();
    document.getElementById('btn-sync')?.addEventListener('click', async function() {
        const statusEl = document.getElementById('sync-status');
        this.disabled = true;
        statusEl.textContent = '同步中...';
        syncLiveLog.style.display = 'block';
        logContainer.innerHTML = '';
        logCount = 0;
        if (logCountEl) logCountEl.textContent = '0 条';
        try {
            const resp = await fetch('/api/sync/run', { method: 'POST' });
            const data = await resp.json();
            if (!resp.ok) {
                statusEl.textContent = '错误: ' + (data.error || '未知错误');
                this.disabled = false;
            }
        } catch (e) {
            statusEl.textContent = '请求失败: ' + e.message;
            this.disabled = false;
        }
    });
});
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```powershell
git add app/templates/dashboard.html
git commit -m "style: update dashboard with new stat-card classes and breadcrumb"
```

---

### Task 4: Update config.html — accordion card groups

**Files:**
- Modify: `app/templates/config.html`

Wrap each config section in an accordion-style collapsible card. Add breadcrumb, status labels, and icon headers.

- [ ] **Step 1: Rewrite `config.html`**

```html
{% extends "base.html" %}
{% block title %}配置 - 飞牛观影同步{% endblock %}
{% block breadcrumb %}<a href="/">首页</a> / <span class="current">配置</span>{% endblock %}

{% block content %}
<h1 class="page-title">配置</h1>

{% if message %}
<div class="alert alert-success alert-dismissible fade show alert-custom">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
{% endif %}
{% if error %}
<div class="alert alert-danger alert-dismissible fade show alert-custom">{{ error }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
{% endif %}

<form method="POST" class="accordion-custom">

    <!-- ── FNTV 数据库 ── -->
    <div class="card-custom">
        <div class="card-header-custom" onclick="toggleCard(this)">
            <div>
                <span style="font-size:16px;margin-right:8px">🗄️</span>
                <strong>FNTV 数据库</strong>
                {% if db_ok %}
                <span class="badge-custom" style="background:#d1fae5;color:#065f46;margin-left:8px">已连接</span>
                {% else %}
                <span class="badge-custom" style="background:#fee2e2;color:#991b1b;margin-left:8px">未连接</span>
                {% endif %}
            </div>
            <span class="arrow open">▼</span>
        </div>
        <div class="card-body-custom open">
            <div class="mb-3">
                <label class="form-label">数据库路径 <span class="text-muted small">（Docker 容器内路径，需通过 volume 挂载）</span></label>
                <div class="input-group">
                    <input type="text" class="form-control" name="fntv_db_path" value="{{ config.fntv_db_path }}" placeholder="/fntv-db/trimmedia.db">
                    <button type="button" class="btn btn-outline-secondary" id="btn-test-db">测试连接</button>
                </div>
                <div id="db-status" class="mt-1 small">
                    {% if db_ok %}<span class="text-success">✓ 已连接</span>
                    {% elif db_error %}<span class="text-danger">✗ {{ db_error }}</span>
                    {% else %}<span class="text-muted">未测试</span>{% endif %}
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">同步用户</label>
                <select class="form-select" name="selected_user">
                    <option value="">-- 请选择用户 --</option>
                    {% for u in users %}
                    <option value="{{ u.guid }}" {% if u.guid == config.selected_user %}selected{% endif %}>{{ u.username }}</option>
                    {% endfor %}
                </select>
                {% if not db_ok %}<div class="text-muted small mt-1">请先测试数据库连接，成功后自动加载用户列表</div>{% endif %}
            </div>
        </div>
    </div>

    <!-- ── 豆瓣账号 ── -->
    <div class="card-custom">
        <div class="card-header-custom" onclick="toggleCard(this)">
            <div>
                <span style="font-size:16px;margin-right:8px">📖</span>
                <strong>豆瓣账号</strong>
                {% if cookie_set %}
                <span class="badge-custom" style="background:#d1fae5;color:#065f46;margin-left:8px">已设置</span>
                {% else %}
                <span class="badge-custom" style="background:#fee2e2;color:#991b1b;margin-left:8px">未设置</span>
                {% endif %}
            </div>
            <span class="arrow open">▼</span>
        </div>
        <div class="card-body-custom open">
            <div class="mb-3">
                <label class="form-label">豆瓣 Cookie</label>
                <textarea class="form-control" name="douban_cookie" rows="2" placeholder="从浏览器复制的完整 Cookie 字符串">{{ config.douban_cookie }}</textarea>
                <div class="mt-2">
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-test-cookie">验证 Cookie</button>
                    <span id="cookie-status" class="ms-2 small"></span>
                </div>
                <div class="text-muted small mt-1">
                    <a href="/cookie-guide" target="_blank">如何获取豆瓣 Cookie？</a>
                </div>
            </div>
        </div>
    </div>

    <!-- ── 同步计划 ── -->
    <div class="card-custom">
        <div class="card-header-custom" onclick="toggleCard(this)">
            <div>
                <span style="font-size:16px;margin-right:8px">🕐</span>
                <strong>同步计划</strong>
            </div>
            <span class="arrow open">▼</span>
        </div>
        <div class="card-body-custom open">
            <!-- mode switch -->
            <div class="mb-3">
                <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" name="sync_mode" value="interval" id="mode_interval"
                           {% if config.sync_mode == 'interval' %}checked{% endif %}>
                    <label class="form-check-label" for="mode_interval">间隔模式</label>
                </div>
                <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" name="sync_mode" value="cron" id="mode_cron"
                           {% if config.sync_mode == 'cron' %}checked{% endif %}>
                    <label class="form-check-label" for="mode_cron">定时模式（Cron）</label>
                </div>
            </div>

            <!-- interval -->
            <div id="interval-config" {% if config.sync_mode == 'cron' %}style="display:none"{% endif %}>
                <div class="row align-items-center g-2">
                    <div class="col-auto"><label class="form-label mb-0">每</label></div>
                    <div class="col-auto">
                        <input type="number" class="form-control" name="sync_interval_hours"
                               value="{{ config.sync_interval_hours }}" min="1" max="168" style="width:80px">
                    </div>
                    <div class="col-auto"><span class="form-label mb-0">小时执行一次</span></div>
                </div>
            </div>

            <!-- cron -->
            <div id="cron-config" {% if config.sync_mode != 'cron' %}style="display:none"{% endif %}>
                <!-- quick presets -->
                <div class="mb-3">
                    <label class="form-label small text-muted">快速预设</label>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 3 * * *')">每天 03:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 8 * * *')">每天 08:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 22 * * *')">每天 22:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 8 * * 1')">每周一 08:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 8 * * 1,3,5')">周一三五 08:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 3 1 * *')">每月1日 03:00</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary m-1" onclick="setPreset('0 0 1 1 *')">每年1月1日 00:00</button>
                    </div>
                </div>

                <!-- builder -->
                <div class="row g-2 align-items-center mb-2">
                    <div class="col-auto">
                        <select class="form-select" id="cron_freq" onchange="updateCronUI()" style="width:auto">
                            <option value="daily">每天</option>
                            <option value="weekly">每周</option>
                            <option value="monthly">每月</option>
                            <option value="yearly">每年</option>
                            <option value="custom">自定义</option>
                        </select>
                    </div>
                    <div class="col-auto" id="cron_time_group">
                        <select class="form-select d-inline-block" id="cron_hour" onchange="generateCron()" style="width:80px"></select>
                        <span class="mx-1">:</span>
                        <select class="form-select d-inline-block" id="cron_minute" onchange="generateCron()" style="width:80px"></select>
                    </div>
                    <div class="col-auto" id="cron_dow_group" style="display:none">
                        <span class="text-muted small me-2">星期</span>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_1" value="1" onchange="generateCron()"><label class="form-check-label small" for="dow_1">一</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_2" value="2" onchange="generateCron()"><label class="form-check-label small" for="dow_2">二</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_3" value="3" onchange="generateCron()"><label class="form-check-label small" for="dow_3">三</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_4" value="4" onchange="generateCron()"><label class="form-check-label small" for="dow_4">四</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_5" value="5" onchange="generateCron()"><label class="form-check-label small" for="dow_5">五</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_6" value="6" onchange="generateCron()"><label class="form-check-label small" for="dow_6">六</label></div>
                        <div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="dow_0" value="0" onchange="generateCron()"><label class="form-check-label small" for="dow_0">日</label></div>
                    </div>
                    <div class="col-auto" id="cron_dom_group" style="display:none">
                        <span class="text-muted small me-1">每月的</span>
                        <select class="form-select d-inline-block" id="cron_dom" onchange="generateCron()" style="width:80px"></select><span class="ms-1">日</span>
                    </div>
                    <div class="col-auto" id="cron_month_group" style="display:none">
                        <select class="form-select d-inline-block" id="cron_month" onchange="generateCron()" style="width:80px"></select>
                    </div>
                    <div class="col-auto" id="cron_custom_group" style="display:none">
                        <input type="text" class="form-control" id="cron_raw" placeholder="分 时 日 月 周，如 30 6 * * *" oninput="generateCron()" style="width:260px">
                    </div>
                </div>
                <div class="p-2 bg-light rounded">
                    <span class="text-muted small">Cron：</span>
                    <code id="cron_expr_display">{{ config.sync_cron }}</code>
                    <input type="hidden" name="sync_cron" id="cron_expr" value="{{ config.sync_cron }}">
                    <span class="ms-3 text-success" id="cron_preview"></span>
                </div>
            </div>
        </div>
    </div>

    <!-- ── 同步规则 ── -->
    <div class="card-custom">
        <div class="card-header-custom" onclick="toggleCard(this)">
            <div>
                <span style="font-size:16px;margin-right:8px">⚙️</span>
                <strong>同步规则</strong>
            </div>
            <span class="arrow open">▼</span>
        </div>
        <div class="card-body-custom open">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">播放阈值（%）</label>
                    <div class="input-group">
                        <input type="number" class="form-control" name="watch_threshold_percent" value="{{ config.watch_threshold_percent }}" min="0" max="100">
                        <span class="input-group-text">%</span>
                    </div>
                    <div class="text-muted small">超过此百分比才算已看（0 为不限制）</div>
                </div>
                <div class="col-md-6 mb-3">
                    <div class="form-check mt-4">
                        <input class="form-check-input" type="checkbox" name="private" id="private" {% if config.private %}checked{% endif %}>
                        <label class="form-check-label" for="private">豆瓣标记仅自己可见</label>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Save -->
    <div class="d-flex justify-content-end mt-3">
        <button type="submit" class="btn btn-primary px-4">保存配置</button>
    </div>
</form>
{% endblock %}

{% block scripts %}
<script>
// Accordion card toggle
function toggleCard(header) {
    const body = header.nextElementSibling;
    const arrow = header.querySelector('.arrow');
    body.classList.toggle('open');
    arrow.classList.toggle('open');
}

// ── mode switch ──
document.querySelectorAll('input[name="sync_mode"]').forEach(r => {
    r.addEventListener('change', function() {
        const isCron = this.value === 'cron';
        document.getElementById('interval-config').style.display = isCron ? 'none' : '';
        document.getElementById('cron-config').style.display = isCron ? '' : 'none';
        if (isCron) generateCron();
    });
});

// ── Cron builder ──
function populateSelect(id, start, end, pad = true) {
    const sel = document.getElementById(id);
    for (let i = start; i <= end; i++) {
        const v = pad ? String(i).padStart(2, '0') : String(i);
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = pad ? v : (v + '月');
        sel.appendChild(opt);
    }
}
populateSelect('cron_hour', 0, 23);
populateSelect('cron_minute', 0, 59);
for (let i = 1; i <= 31; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = i + '日';
    document.getElementById('cron_dom').appendChild(opt);
}
for (let i = 1; i <= 12; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = i + '月';
    document.getElementById('cron_month').appendChild(opt);
}

function describeCron(expr) {
    const parts = expr.trim().split(/\s+/);
    if (parts.length !== 5) return '无效表达式';
    const [min, hour, dom, month, dow] = parts;
    const isSimple = /^\d+$/.test(min) && /^\d+$/.test(hour);
    if (!isSimple) return '';
    if (dom === '*' && month === '*' && dow === '*')
        return '→ 每天 ' + hour.padStart(2,'0') + ':' + min.padStart(2,'0');
    if (dom === '*' && month === '*' && /^[\d,]+$/.test(dow)) {
        const days = {0:'日',1:'一',2:'二',3:'三',4:'四',5:'五',6:'六',7:'日'};
        const names = dow.split(',').map(d => '周' + (days[d] || d)).join('、');
        return '→ 每' + names + ' ' + hour.padStart(2,'0') + ':' + min.padStart(2,'0');
    }
    if (/^\d+$/.test(dom) && month === '*' && dow === '*')
        return '→ 每月' + dom + '日 ' + hour.padStart(2,'0') + ':' + min.padStart(2,'0');
    if (/^\d+$/.test(dom) && /^\d+$/.test(month) && dow === '*')
        return '→ 每年' + month + '月' + dom + '日 ' + hour.padStart(2,'0') + ':' + min.padStart(2,'0');
    return '';
}

function generateCron() {
    const freq = document.getElementById('cron_freq').value;
    const hour = document.getElementById('cron_hour').value.padStart(2, '0');
    const minute = document.getElementById('cron_minute').value.padStart(2, '0');
    let cron = '';
    switch (freq) {
        case 'daily': cron = minute + ' ' + hour + ' * * *'; break;
        case 'weekly': {
            const dows = [...document.querySelectorAll('#cron_dow_group input:checked')].map(cb => cb.value).sort((a,b)=>a-b).join(',');
            if (dows) cron = minute + ' ' + hour + ' * * ' + dows;
            break;
        }
        case 'monthly': cron = minute + ' ' + hour + ' ' + document.getElementById('cron_dom').value + ' * *'; break;
        case 'yearly': cron = minute + ' ' + hour + ' ' + document.getElementById('cron_dom').value + ' ' + document.getElementById('cron_month').value + ' *'; break;
        case 'custom': cron = document.getElementById('cron_raw').value.trim(); break;
    }
    if (cron) {
        document.getElementById('cron_expr').value = cron;
        document.getElementById('cron_expr_display').textContent = cron;
        document.getElementById('cron_preview').textContent = describeCron(cron);
    }
}

function updateCronUI() {
    const freq = document.getElementById('cron_freq').value;
    ['cron_time_group','cron_dow_group','cron_dom_group','cron_month_group','cron_custom_group'].forEach(id => document.getElementById(id).style.display = 'none');
    if (freq === 'custom') {
        document.getElementById('cron_custom_group').style.display = 'inline-block';
    } else {
        document.getElementById('cron_time_group').style.display = 'inline-block';
        if (freq === 'weekly') document.getElementById('cron_dow_group').style.display = 'inline-block';
        if (['monthly','yearly'].includes(freq)) document.getElementById('cron_dom_group').style.display = 'inline-block';
        if (freq === 'yearly') document.getElementById('cron_month_group').style.display = 'inline-block';
    }
    generateCron();
}

function applyCron(expr) {
    const parts = expr.trim().split(/\s+/);
    if (parts.length !== 5) return;
    const [min, hour, dom, month, dow] = parts;
    document.getElementById('cron_hour').value = hour.padStart(2, '0');
    document.getElementById('cron_minute').value = min.padStart(2, '0');
    if (dow !== '*') {
        document.getElementById('cron_freq').value = 'weekly';
        document.querySelectorAll('#cron_dow_group input').forEach(cb => cb.checked = false);
        dow.split(',').forEach(d => { const cb = document.querySelector('#cron_dow_group input[value="'+d+'"]'); if (cb) cb.checked = true; });
    } else if (dom !== '*' && month !== '*') { document.getElementById('cron_freq').value = 'yearly'; document.getElementById('cron_month').value = month; document.getElementById('cron_dom').value = dom;
    } else if (dom !== '*') { document.getElementById('cron_freq').value = 'monthly'; document.getElementById('cron_dom').value = dom;
    } else { document.getElementById('cron_freq').value = 'daily'; }
    updateCronUI();
}

function setPreset(expr) {
    document.getElementById('mode_cron').checked = true;
    document.getElementById('mode_cron').dispatchEvent(new Event('change'));
    applyCron(expr);
}

document.addEventListener('DOMContentLoaded', function () {
    const currentCron = '{{ config.sync_cron }}';
    if ('{{ config.sync_mode }}' === 'cron' && currentCron) {
        setTimeout(function () { applyCron(currentCron); }, 50);
    }
});

// ── Test DB ──
document.getElementById('btn-test-db')?.addEventListener('click', async function() {
    const path = document.querySelector('input[name="fntv_db_path"]').value;
    const statusEl = document.getElementById('db-status');
    statusEl.innerHTML = '<span class="text-muted">测试中...</span>';
    try {
        const resp = await fetch('/api/fntv/test-db', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({db_path: path}) });
        const data = await resp.json();
        if (data.ok) {
            statusEl.innerHTML = '<span class="text-success">✓ 连接成功</span>';
            const userResp = await fetch('/api/fntv/users?db_path=' + encodeURIComponent(path));
            const userData = await userResp.json();
            if (userData.users) {
                const sel = document.querySelector('select[name="selected_user"]');
                sel.innerHTML = '<option value="">-- 请选择用户 --</option>' + userData.users.map(u => '<option value="'+u.guid+'">'+u.username+'</option>').join('');
            }
        } else {
            statusEl.innerHTML = '<span class="text-danger">✗ ' + (data.error || '连接失败') + '</span>';
        }
    } catch (e) { statusEl.innerHTML = '<span class="text-danger">✗ 请求失败: ' + e.message + '</span>'; }
});

// ── Test Cookie ──
document.getElementById('btn-test-cookie')?.addEventListener('click', async function() {
    const cookie = document.querySelector('textarea[name="douban_cookie"]').value;
    const statusEl = document.getElementById('cookie-status');
    statusEl.textContent = '验证中...';
    try {
        const resp = await fetch('/api/douban/check-cookie', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cookie: cookie}) });
        const data = await resp.json();
        statusEl.textContent = data.ok ? '✓ Cookie 有效' : '✗ Cookie 无效';
        statusEl.className = 'ms-2 small ' + (data.ok ? 'text-success' : 'text-danger');
    } catch (e) { statusEl.textContent = '✗ 请求失败'; statusEl.className = 'ms-2 small text-danger'; }
});
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```powershell
git add app/templates/config.html
git commit -m "style: refactor config page into accordion card groups with status labels"
```

---

### Task 5: Update history.html — table styling

**Files:**
- Modify: `app/templates/history.html`

Update table to use new CSS classes, add breadcrumb, improve empty state and pagination.

- [ ] **Step 1: Rewrite `history.html`**

```html
{% extends "base.html" %}
{% block title %}同步日志 - 飞牛观影同步{% endblock %}
{% block breadcrumb %}<a href="/">首页</a> / <span class="current">同步日志</span>{% endblock %}

{% block content %}
<h1 class="page-title">同步日志</h1>

<div class="card-custom p-0">
    <div class="table-responsive">
        <table class="table-custom table table-hover">
            <thead>
                <tr>
                    <th style="width:160px">时间</th>
                    <th style="width:100px">操作</th>
                    <th>标题</th>
                    <th>详情</th>
                </tr>
            </thead>
            <tbody>
                {% for log in logs %}
                <tr>
                    <td class="small text-nowrap">
                        {% if log.created_at %}
                            {{ log.created_at | timestamp_to_dt }}
                        {% endif %}
                    </td>
                    <td>
                        <span class="badge bg-{{ 'success' if 'done' in log.action else 'info' if 'doing' in log.action else 'warning' if 'skip' in log.action else 'danger' }}">
                            {{ log.action }}
                        </span>
                    </td>
                    <td>{{ log.series_title or '-' }}</td>
                    <td class="small text-muted">{{ log.detail[:80] }}</td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="4">
                        <div class="empty-state">
                            <div class="empty-icon">📋</div>
                            <p class="mb-0">暂无同步日志</p>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<nav class="mt-3 d-flex justify-content-between align-items-center">
    <span class="small text-muted">页码 {{ page }}</span>
    <ul class="pagination pagination-sm pagination-custom mb-0">
        <li class="page-item {% if page <= 1 %}disabled{% endif %}">
            <a class="page-link" href="?page={{ page - 1 }}">上一页</a>
        </li>
        <li class="page-item {% if logs|length < 20 %}disabled{% endif %}">
            <a class="page-link" href="?page={{ page + 1 }}">下一页</a>
        </li>
    </ul>
</nav>
{% endblock %}
```

- [ ] **Step 2: Commit**

```powershell
git add app/templates/history.html
git commit -m "style: update history page with new table styling and empty state"
```

---

### Task 6: Refactor cookie_guide.html — use base.html

**Files:**
- Modify: `app/templates/cookie_guide.html`

Convert from standalone HTML page to extending base.html. Keep step card layout.

- [ ] **Step 1: Rewrite `cookie_guide.html`**

```html
{% extends "base.html" %}
{% block title %}Cookie 获取指南 - 飞牛观影同步{% endblock %}
{% block breadcrumb %}<a href="/">首页</a> / <a href="/config">配置</a> / <span class="current">Cookie 获取指南</span>{% endblock %}

{% block head %}
<style>
.guide-step {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-card);
    padding: 1.25rem 1.5rem;
    margin-bottom: .75rem;
    box-shadow: var(--shadow-card);
    transition: box-shadow .2s ease;
}
.guide-step:hover {
    box-shadow: var(--shadow-card-hover);
}
.step-number {
    display: inline-flex;
    width: 30px; height: 30px;
    align-items: center; justify-content: center;
    background: var(--color-primary);
    color: #fff;
    border-radius: 50%;
    font-weight: 700;
    font-size: 14px;
    margin-right: 10px;
    flex-shrink: 0;
}
.step-title {
    font-weight: 600;
    font-size: 1rem;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
}
code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: .9em;
}
</style>
{% endblock %}

{% block content %}
<h1 class="page-title">豆瓣 Cookie 获取指南</h1>
<p class="text-muted mb-4">将豆瓣的登录凭证（Cookie）填入同步工具，以便自动标记观影状态。</p>

<div class="guide-step">
    <div class="step-title"><span class="step-number">1</span>登录豆瓣</div>
    <p class="mb-0">在浏览器中打开 <a href="https://movie.douban.com/" target="_blank">movie.douban.com</a> 并登录你的账号。</p>
</div>

<div class="guide-step">
    <div class="step-title"><span class="step-number">2</span>打开开发者工具</div>
    <p class="mb-0">按 <kbd>F12</kbd> 键打开开发者工具，切换到 <strong>Network（网络）</strong> 标签页。</p>
</div>

<div class="guide-step">
    <div class="step-title"><span class="step-number">3</span>捕获请求</div>
    <p class="mb-0">刷新页面，在网络面板中找到第一个 <code>movie.douban.com</code> 的请求（类型为 <code>document</code>）。</p>
</div>

<div class="guide-step">
    <div class="step-title"><span class="step-number">4</span>复制 Cookie</div>
    <p class="mb-0">点击该请求 → 在右侧 <strong>Request Headers</strong> 中找到 <code>Cookie:</code> 这一行 → 右键选择 <strong>Copy Value</strong>。将完整的 Cookie 字符串粘贴到配置页的输入框中。</p>
</div>

<div class="guide-step">
    <div class="step-title"><span class="step-number">5</span>保存配置</div>
    <p class="mb-0">回到配置页，点击"保存配置"。然后点击"验证 Cookie"确认有效。完成后前往状态页点击"立即同步"开始同步。</p>
</div>

<div class="alert alert-info mt-3" style="border-radius:var(--radius-card);border:none;">
    <strong>注意事项：</strong>
    <ul class="mb-0 mt-1">
        <li>豆瓣 Cookie 通常有效期为 1-3 个月，过期后同步会返回 403 错误，届时重新获取即可</li>
        <li>请不要异地登录频繁切换，否则可能触发风控</li>
        <li>建议使用小号或主账号均可，同步操作仅标记"在看"和"看过"，不会发布其他内容</li>
    </ul>
</div>

<div class="mt-3">
    <a href="/config" class="btn btn-primary">返回配置页</a>
</div>
{% endblock %}
```

Note: We keep the guide-step styles inline via `{% block head %}` because they are specific to this page. The `card-custom` CSS variables (`--color-card`, `--color-border`, etc.) defined in `style.css` are reused here for consistency.

- [ ] **Step 2: Commit**

```powershell
git add app/templates/cookie_guide.html
git commit -m "refactor: convert cookie guide from standalone page to base.html child template"
```

---

### Verification

- [ ] **Start dev server and verify**

```powershell
python -m app
```

- [ ] **Check each page manually:**
  - http://localhost:5000/ — dashboard with sidebar, stat cards, sync button
  - http://localhost:5000/config — accordion card groups with collapse
  - http://localhost:5000/history — styled table with empty state
  - http://localhost:5000/cookie-guide — inherits sidebar layout
  - Resize browser to <768px to verify responsive sidebar collapse

- [ ] **Quick visual regression checks:**
  - Sidebar highlights current page correctly (check each page)
  - Accordion cards open/close on header click
  - Breadcrumb shows correct path on each page
  - Stat cards show proper color coding
  - Log terminal renders correctly
