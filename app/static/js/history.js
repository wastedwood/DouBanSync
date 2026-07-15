(() => {
    const filter = document.getElementById('history-filter');
    const search = document.getElementById('history-search');
    const count = document.getElementById('history-count');
    const noMatch = document.getElementById('history-no-match');
    const rows = [...document.querySelectorAll('.history-row')];
    if (!filter || !search || !count || !noMatch) return;

    const update = () => {
        const tone = filter.value;
        const query = search.value.trim().toLocaleLowerCase('zh-CN');
        let visible = 0;
        rows.forEach((row) => {
            const matchesTone = tone === 'all' || row.dataset.tone === tone;
            const matchesTitle = !query || row.dataset.title.includes(query);
            row.hidden = !(matchesTone && matchesTitle);
            if (!row.hidden) visible += 1;
        });
        noMatch.hidden = visible !== 0 || rows.length === 0;
        count.textContent = `显示 ${visible} 条`;
    };

    filter.addEventListener('change', update);
    search.addEventListener('input', update);
})();
