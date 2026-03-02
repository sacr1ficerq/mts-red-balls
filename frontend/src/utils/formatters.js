// Formatting utilities
window.Formatters = {
    formatTime(timestamp) {
        if (!timestamp) return '';
        return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },

    formatDate(timestamp) {
        if (!timestamp) return '';
        return new Date(timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    },

    formatNumber(num) {
        return new Intl.NumberFormat().format(num || 0);
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    truncateUrl(url) {
        try {
            const parsed = new URL(url.startsWith('http') ? url : 'http://' + url);
            return parsed.hostname + (parsed.pathname !== '/' ? parsed.pathname : '');
        } catch {
            return url.substring(0, 50);
        }
    },

    formatToolInput(input) {
        if (!input) return '';
        try {
            const obj = typeof input === 'string' ? JSON.parse(input) : input;
            let html = '<div class="tool-params">';
            for (const [key, value] of Object.entries(obj)) {
                let valStr = typeof value === 'object' ? JSON.stringify(value) : String(value);
                if (valStr.length > 200) valStr = valStr.substring(0, 200) + '...';
                html += `<div class="param-row"><span class="param-key">${key}:</span> <span class="param-value">${this.escapeHtml(valStr)}</span></div>`;
            }
            html += '</div>';
            return html;
        } catch {
            return this.escapeHtml(String(input));
        }
    },

    formatToolOutput(output, toolName) {
        if (!output) return '';
        
        if (toolName === 'search') {
            const lines = output.split('\n');
            let html = '<div class="search-results-container">';
            let inResult = false, resultNum = 0, currentTitle = '', currentSource = '', currentBody = [];
            
            for (const line of lines) {
                if (line.match(/^\d+\.\s/)) {
                    if (inResult && currentTitle) html += this.buildSearchResultCard(resultNum, currentTitle, currentSource, currentBody);
                    resultNum++;
                    currentTitle = line.replace(/^\d+\.\s*/, '').trim();
                    currentSource = '';
                    currentBody = [];
                    inResult = true;
                } else if (line.startsWith('   Source:')) {
                    currentSource = line.replace('   Source:', '').trim();
                } else if (line.trim() && !line.startsWith('Search results')) {
                    const body = line.replace(/^   /, '').trim();
                    if (body) currentBody.push(body);
                }
            }
            if (inResult && currentTitle) html += this.buildSearchResultCard(resultNum, currentTitle, currentSource, currentBody);
            html += '</div>';
            return html;
        }
        
        if (toolName === 'console') return '<pre class="console-output">' + this.escapeHtml(output) + '</pre>';
        if (toolName === 'files') return '<pre class="files-output">' + this.escapeHtml(output) + '</pre>';
        
        return '<pre class="text-xs font-mono">' + this.escapeHtml(output) + '</pre>';
    },

    buildSearchResultCard(num, title, source, body) {
        const bodyHtml = body.length > 0 
            ? '<div class="search-body">' + this.escapeHtml(body.join(' ')).substring(0, 300) + (body.join(' ').length > 300 ? '...' : '') + '</div>' 
            : '';
        const sourceHtml = source 
            ? `<a href="${this.escapeHtml(source)}" target="_blank" class="search-source">${this.escapeHtml(this.truncateUrl(source))}</a>` 
            : '';
        
        return `<div class="search-result-card">
            <div class="search-result-number">${num}</div>
            <div class="search-result-content">
                <div class="search-title">${this.escapeHtml(title)}</div>
                ${bodyHtml}
                ${sourceHtml}
            </div>
        </div>`;
    },

    formatContent(content) {
        if (!content) return '';
        if (content.trim().startsWith('{')) {
            try {
                const json = JSON.parse(content);
                if (json.action === 'tool') return '<span class="text-gray-400 italic">Выполнение инструмента...</span>'; 
                if (json.action === 'delegate' && json.agent && json.task) {
                    const names = {'Coordinator': 'Планировщик', 'CodeAgent': 'Программист', 'SearchAgent': 'Поисковик', 'CriticAgent': 'Критик'};
                    return `<span class="text-purple-600">→ ${names[json.agent] || json.agent}:</span> ${json.task.substring(0, 100)}...`;
                }
                if (json.action === 'done' && json.result) return json.result;
                return '<span class="text-gray-400 italic">Обработка...</span>';
            } catch (e) {}
        }
        return content;
    }
};
