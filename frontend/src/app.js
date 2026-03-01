// Main application logic
window.dashboard = function() {
    return {
        // State
        socket: null,
        eventSource: null,
        isConnected: false,
        sidebarOpen: true,
        newTaskInput: '',
        currentSessionId: null,
        activeSessions: {},
        historicalSessions: [],
        _currentSessionData: null,
        metrics: { total_tokens: 0, total_cost: 0 },
        autoScrollEnabled: true,
        fileTree: null,
        fileTreeOpen: true,
        fileTreeOpenPaths: {},
        expandedEvents: {},
        currentPlan: null,

        // Initialize
        init() {
            this.fetchSessions();
            this.fetchFileTree();
            this.$watch('currentSessionId', () => this.onSessionChange());
        },

        // Session management
        async fetchSessions() {
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                
                const savedExpanded = {};
                if (this.currentSessionId) {
                    for (const [key, value] of Object.entries(this.expandedEvents)) {
                        if (key.startsWith(this.currentSessionId)) {
                            savedExpanded[key] = value;
                        }
                    }
                }
                
                this.activeSessions = data.active || {};
                this.historicalSessions = data.historical || [];
                
                if (this.currentSessionId) {
                    for (const key of Object.keys(savedExpanded)) {
                        this.expandedEvents[key] = savedExpanded[key];
                    }
                }
                
                if (this.currentSessionId && this.activeSessions[this.currentSessionId]?.events) {
                    const events = this.activeSessions[this.currentSessionId].events;
                    events.forEach((event, index) => {
                        const eventKey = `${this.currentSessionId}-${index}`;
                        if (savedExpanded.hasOwnProperty(eventKey)) {
                            event.expanded = savedExpanded[eventKey];
                            this.expandedEvents[eventKey] = savedExpanded[eventKey];
                        } else if (event.expanded === undefined) {
                            event.expanded = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
                            this.expandedEvents[eventKey] = event.expanded;
                        } else {
                            this.expandedEvents[eventKey] = event.expanded;
                        }
                    });
                    this.activeSessions[this.currentSessionId].events = [...events];
                    this.currentSession = this.activeSessions[this.currentSessionId];
                }
                
                if (this.currentSession && this.currentSession.events) {
                    this.currentSession.events.forEach((event, index) => {
                        const eventKey = `${this.currentSessionId}-${index}`;
                        if (this.expandedEvents.hasOwnProperty(eventKey)) {
                            event.expanded = this.expandedEvents[eventKey];
                        }
                    });
                }
            } catch(e) {
                console.log('Waiting for backend...');
            }
        },

        async fetchSessionData(sessionId) {
            try {
                const res = await fetch(`/api/session/${sessionId}`);
                const data = await res.json();
                
                if (data.events) {
                    data.events.forEach((event, index) => {
                        const eventKey = `${sessionId}-${index}`;
                        if (this.expandedEvents.hasOwnProperty(eventKey)) {
                            event.expanded = this.expandedEvents[eventKey];
                        } else {
                            event.expanded = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
                            this.expandedEvents[eventKey] = event.expanded;
                        }
                    });
                }
                
                if (data.total_tokens) {
                    this.metrics.total_tokens = data.total_tokens;
                    this.metrics.total_cost = data.total_cost || 0;
                }
                
                if (this.historicalSessions.find(s => s.id === sessionId)) {
                    this._currentSessionData = data;
                } else {
                    this.activeSessions[sessionId] = data;
                }
            } catch(e) {
                console.log('Error fetching session:', e);
            }
        },

        createNewSession() {
            this.currentSessionId = null;
            this.newTaskInput = '';
            this.metrics = { total_tokens: 0, total_cost: 0 };
            this._currentSessionData = null;
            this.expandedEvents = {};
        },

        async clearHistory() {
            if (!confirm('Очистить всю историю?')) return;
            try {
                await fetch('/api/sessions/clear', { method: 'POST' });
                this.historicalSessions = [];
                this.activeSessions = {};
                this.currentSessionId = null;
            } catch(e) {
                console.error('Error clearing history:', e);
            }
        },

        get currentSession() {
            if (!this.currentSessionId) return null;
            if (this.activeSessions[this.currentSessionId]) {
                return this.activeSessions[this.currentSessionId];
            }
            const hist = this.historicalSessions.find(s => s.id === this.currentSessionId);
            if (hist) return hist;
            if (this._currentSessionData && this._currentSessionData.id === this.currentSessionId) {
                return this._currentSessionData;
            }
            return null;
        },

        get currentSessionEvents() {
            if (!this.currentSession || !this.currentSession.events) return [];
            
            const events = this.currentSession.events;
            
            for (const event of events) {
                if (event.type === 'thought' && event.data && event.data.content) {
                    try {
                        const content = event.data.content;
                        if (content.includes('"plan"') && content.includes('"steps"')) {
                            const planMatch = content.match(/\{[\s\S]*"plan"[\s\S]*"steps"\s*:\s*\[[\s\S]*\]\}/);
                            if (planMatch) {
                                const plan = JSON.parse(planMatch[0]);
                                if (plan.plan && plan.steps) {
                                    this.currentPlan = plan;
                                    break;
                                }
                            }
                        }
                        if (content.includes('"plan_update"') || content.includes('"step_id"')) {
                            const updateMatch = content.match(/\{"plan_update"\s*:\s*\{"step_id"\s*:\s*(\d+)\s*,\s*"status"\s*:\s*"(\w+)"\}\}/);
                            if (updateMatch && this.currentPlan && this.currentPlan.steps) {
                                const stepId = parseInt(updateMatch[1]);
                                const status = updateMatch[2];
                                const step = this.currentPlan.steps.find(s => s.id === stepId);
                                if (step) {
                                    step.status = status;
                                }
                            }
                        }
                    } catch(e) {}
                }
                if (event.type === 'delegate' && event.data && event.data.step_id) {
                    if (this.currentPlan && this.currentPlan.steps) {
                        const step = this.currentPlan.steps.find(s => s.id === event.data.step_id);
                        if (step) {
                            step.status = 'active';
                        }
                    }
                }
            }
            
            return events;
        },

        get sortedActiveSessions() {
            return Object.values(this.activeSessions)
                .filter(s => s.created_at)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        },

        get sortedHistoricalSessions() {
            return [...this.historicalSessions]
                .filter(s => s.created_at)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        },

        selectSession(id) {
            this.currentSessionId = id;
            this.currentPlan = null;
            const isActive = this.activeSessions && this.activeSessions[id] && this.activeSessions[id].status === 'running';
            if (isActive) {
                this.connectSSE(id);
            } else {
                this.fetchSessionData(id);
            }
        },

        async stopSession() {
            if (!this.currentSessionId) return;
            try {
                await fetch(`/api/session/${this.currentSessionId}/stop`, { method: 'POST' });
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
                await this.fetchSessions();
            } catch(e) {
                console.error('Error stopping session:', e);
            }
        },

        async startTask() {
            if (!this.newTaskInput.trim()) return;
            
            const task = this.newTaskInput;
            this.newTaskInput = '';
            
            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: task })
                });
                const data = await res.json();
                this.currentSessionId = data.session_id;
                
                await this.fetchSessions();
                this.connectSSE(data.session_id);
            } catch(e) {
                console.error('Error starting task:', e);
            }
        },

        connectSSE(sessionId) {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            
            this.fetchSessionData(sessionId);
            
            this.eventSource = new EventSource(`/api/sse/${sessionId}`);
            
            this.eventSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    
                    if (event.type === 'session_done') {
                        if (this.activeSessions[sessionId]) {
                            this.activeSessions[sessionId].status = event.status || 'completed';
                        }
                        return;
                    }
                    
                    if (this.currentSessionId === sessionId) {
                        if (!this.activeSessions[sessionId]) {
                            this.activeSessions[sessionId] = { events: [], status: 'running' };
                        }
                        if (!this.activeSessions[sessionId].events) {
                            this.activeSessions[sessionId].events = [];
                        }
                        
                        const existingEvents = this.activeSessions[sessionId].events;
                        const isDuplicate = existingEvents.some(
                            (ev, i) => ev.type === event.type && 
                                       ev.timestamp === event.timestamp &&
                                       JSON.stringify(ev.data) === JSON.stringify(event.data)
                        );
                        if (isDuplicate) return;
                        
                        const eventIndex = existingEvents.length;
                        const eventKey = `${sessionId}-${eventIndex}`;
                        
                        if (!this.expandedEvents.hasOwnProperty(eventKey)) {
                            this.expandedEvents[eventKey] = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
                        }
                        
                        event.expanded = this.expandedEvents[eventKey];
                        this.activeSessions[sessionId].events.push(event);
                        this.$nextTick(() => this.scrollToBottom());
                    }
                } catch(err) {
                    console.error('SSE parse error:', err);
                }
            };
            
            this.eventSource.onerror = () => {
                const session = this.activeSessions[sessionId];
                if (session && session.status === 'running') {
                    console.log('SSE connection lost, retrying...');
                    this.eventSource.close();
                    setTimeout(() => {
                        if (this.currentSessionId === sessionId && this.activeSessions[sessionId]?.status === 'running') {
                            this.connectSSE(sessionId);
                        }
                    }, 2000);
                } else {
                    console.log('SSE connection closed');
                    this.eventSource.close();
                    this.eventSource = null;
                }
            };
        },

        async fetchFileTree() {
            try {
                const res = await fetch('/api/workspace/files');
                const data = await res.json();
                this.fileTree = data.tree || {};
            } catch(e) {
                console.log('Error fetching files:', e);
            }
        },

        async readFile(path) {
            try {
                const res = await fetch(`/api/workspace/read?path=${encodeURIComponent(path)}`);
                const data = await res.json();
                return data.content || data.error || 'Пустой файл';
            } catch(e) {
                return 'Ошибка чтения файла';
            }
        },

        toggleFolder(path) {
            if (this.fileTreeOpenPaths[path]) {
                delete this.fileTreeOpenPaths[path];
            } else {
                this.fileTreeOpenPaths[path] = true;
            }
        },

        toggleEvent(sessionId, index) {
            const eventKey = `${sessionId}-${index}`;
            const currentState = this.expandedEvents[eventKey];
            const isExpanded = currentState !== undefined ? currentState : ['result', 'error', 'tool', 'delegate', 'system'].includes(this.currentSession?.events?.[index]?.type);
            
            this.expandedEvents[eventKey] = !isExpanded;
            
            if (this.currentSession && this.currentSession.events && this.currentSession.events[index]) {
                this.currentSession.events[index].expanded = !isExpanded;
                this.currentSession.events = [...this.currentSession.events];
            }
        },

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

        scrollToBottom() {
            const el = document.getElementById('events-feed');
            if (el) {
                const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
                if (isNearBottom || this.currentSessionEvents.length < 2) {
                    el.scrollTop = el.scrollHeight;
                }
            }
        },

        onSessionChange() {
            this.fetchFileTree();
        },

        // Agent functions
        getAgentDisplayName(agent) {
            if (!agent) return 'Агент';
            const names = {
                'Coordinator': 'Планировщик',
                'CoordinatorAgent': 'Планировщик',
                'CodeAgent': 'Программист',
                'Code': 'Программист',
                'SearchAgent': 'Поисковик',
                'Search': 'Поисковик',
                'CriticAgent': 'Критик',
                'Critic': 'Критик',
                'CreatorAgent': 'Создатель',
                'Creator': 'Создатель',
                'Analyst': 'Аналитик'
            };
            return names[agent] || agent;
        },

        getAgentIcon(agent) {
            const icons = {
                'Coordinator': 'fa-sitemap',
                'CodeAgent': 'fa-code',
                'SearchAgent': 'fa-search',
                'CriticAgent': 'fa-glasses',
                'Creator': 'fa-pen',
                'Analyst': 'fa-chart-line'
            };
            return icons[agent] || 'fa-robot';
        },

        getAgentStyle(agent) {
            return { 
                bg: 'bg-blue-50', 
                border: 'border-blue-200', 
                text: 'text-blue-700', 
                icon: this.getAgentIcon(agent),
                iconColor: 'text-blue-600',
                headerBg: 'bg-blue-50'
            };
        },

        getUserStyle() {
            return {
                icon: 'fa-user',
                bg: 'bg-red-50',
                border: 'border-red-200',
                headerBg: 'bg-red-50',
                text: 'text-red-700',
                iconColor: 'text-red-600'
            };
        },

        getToolStyle(toolName) {
            return {
                icon: toolName === 'search' ? 'fa-search' : toolName === 'console' ? 'fa-terminal' : 'fa-file-code',
                bg: 'bg-emerald-50',
                border: 'border-emerald-200',
                headerBg: 'bg-emerald-50',
                text: 'text-emerald-700',
                iconColor: 'text-emerald-600'
            };
        },

        getDelegateStyle() {
            return {
                icon: 'fa-share-alt',
                bg: 'bg-purple-50',
                border: 'border-purple-200',
                headerBg: 'bg-purple-50',
                text: 'text-purple-700',
                iconColor: 'text-purple-600'
            };
        },

        escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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
                let inResult = false;
                let resultNum = 0;
                let currentTitle = '';
                let currentSource = '';
                let currentBody = [];
                
                for (const line of lines) {
                    if (line.match(/^\d+\.\s/)) {
                        if (inResult && currentTitle) {
                            html += this.buildSearchResultCard(resultNum, currentTitle, currentSource, currentBody);
                        }
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
                if (inResult && currentTitle) {
                    html += this.buildSearchResultCard(resultNum, currentTitle, currentSource, currentBody);
                }
                html += '</div>';
                return html;
            }
            
            if (toolName === 'console') {
                return '<pre class="console-output">' + this.escapeHtml(output) + '</pre>';
            }
            
            if (toolName === 'files') {
                return '<pre class="files-output">' + this.escapeHtml(output) + '</pre>';
            }
            
            return '<pre class="text-xs font-mono">' + this.escapeHtml(output) + '</pre>';
        },

        buildSearchResultCard(num, title, source, body) {
            const bodyHtml = body.length > 0 
                ? '<div class="search-body">' + this.escapeHtml(body.join(' ')).substring(0, 300) + (body.join(' ').length > 300 ? '...' : '') + '</div>' 
                : '';
            const sourceHtml = source 
                ? `<a href="${this.escapeHtml(source)}" target="_blank" class="search-source">${this.escapeHtml(this.truncateUrl(source))}</a>` 
                : '';
            
            return `
                <div class="search-result-card">
                    <div class="search-result-number">${num}</div>
                    <div class="search-result-content">
                        <div class="search-title">${this.escapeHtml(title)}</div>
                        ${bodyHtml}
                        ${sourceHtml}
                    </div>
                </div>
            `;
        },

        truncateUrl(url) {
            try {
                const parsed = new URL(url.startsWith('http') ? url : 'http://' + url);
                return parsed.hostname + (parsed.pathname !== '/' ? parsed.pathname : '');
            } catch {
                return url.substring(0, 50);
            }
        },

        formatContent(content) {
            if (!content) return '';
            
            if (content.trim().startsWith('{')) {
                try {
                    const json = JSON.parse(content);
                    
                    if (json.action === 'tool') {
                        return '<span class="text-gray-400 italic">Выполнение инструмента...</span>'; 
                    }
                    
                    if (json.action === 'delegate' && json.agent && json.task) {
                        return `<span class="text-purple-600">→ ${this.getAgentDisplayName(json.agent)}:</span> ${json.task.substring(0, 100)}...`;
                    }
                    
                    if (json.action === 'done' && json.result) {
                        return json.result;
                    }
                    
                        return '<span class="text-gray-400 italic">Обработка...</span>';
                } catch (e) {}
            }
            
            return content;
        }
    };
};
