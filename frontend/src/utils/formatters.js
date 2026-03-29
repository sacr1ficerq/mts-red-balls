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
        if (!input) return '<div class="text-gray-400 italic">Нет входных данных</div>';
        try {
            const obj = typeof input === 'string' ? JSON.parse(input) : input;
            let html = '<div class="tool-params">';
            for (const [key, value] of Object.entries(obj)) {
                let valStr = typeof value === 'object' ? JSON.stringify(value) : String(value);
                // Truncate long values but show more than before
                if (valStr.length > 500) valStr = valStr.substring(0, 500) + '...';
                html += `<div class="param-row"><span class="param-key">${key}:</span> <span class="param-value whitespace-pre-wrap break-all">${this.escapeHtml(valStr)}</span></div>`;
            }
            html += '</div>';
            return html;
        } catch {
            return this.escapeHtml(String(input));
        }
    },

    formatToolOutput(output, toolName) {
        if (!output) return '<div class="text-gray-400 italic">Пустой вывод</div>';
        
        // Truncate very long output to prevent UI issues
        const MAX_LENGTH = 50000;
        let displayOutput = output;
        let truncated = false;
        if (output.length > MAX_LENGTH) {
            displayOutput = output.substring(0, MAX_LENGTH) + '\n\n... (вывод обрезан)';
            truncated = true;
        }
        
        if (toolName === 'search') {
            const lines = displayOutput.split('\n');
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
            if (truncated) html += '<div class="text-yellow-600 text-xs mt-2">⚠️ Вывод был обрезан из-за большого размера</div>';
            return html;
        }
        
        if (toolName === 'console') return '<pre class="console-output">' + this.escapeHtml(displayOutput) + '</pre>';
        if (toolName === 'files') return '<pre class="files-output">' + this.escapeHtml(displayOutput) + '</pre>';
        
        let result = '<pre class="text-xs font-mono whitespace-pre-wrap break-all">' + this.escapeHtml(displayOutput) + '</pre>';
        if (truncated) result += '<div class="text-yellow-600 text-xs mt-2">⚠️ Вывод был обрезан из-за большого размера</div>';
        return result;
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
        
        // If it looks like just thinking/reasoning (no JSON), show nothing
        if (!content.trim().startsWith('{')) {
            return '';
        }
        
        if (content.trim().startsWith('{')) {
            try {
                const json = JSON.parse(content);
                if (json.action === 'tool') {
                    return '<span class="text-emerald-600 font-medium">⚙️ ' + (json.tool || 'tool') + '</span>';
                }
                if (json.action === 'delegate' && json.agent && json.task) {
                    const names = {'Coordinator': 'Планировщик', 'CodeAgent': 'Программист', 'SearchAgent': 'Поисковик', 'CriticAgent': 'Критик'};
                    return `<span class="text-purple-600">→ ${names[json.agent] || json.agent}:</span> ${json.task.substring(0, 100)}...`;
                }
                if (json.action === 'done' && json.result) return json.result;
                if (json.action === 'plan') return '<span class="text-amber-600 font-medium">📋 План: ' + (json.steps?.length || 0) + ' шагов</span>';
                if (json.action === 'update_plan') return '<span class="text-orange-600 font-medium">✏️ Обновление плана</span>';
                return '';
            } catch (e) {}
        }
        return content;
    }
};
