window.dashboard = function() {
    return {
        socket: null,
        eventSource: null,
        isConnected: false,
        sidebarOpen: true,
        newTaskInput: '',
        currentSessionId: null,
        activeSessions: {},
        historicalSessions: [],
        _currentSession: null,
        metrics: { total_tokens: 0, total_cost: 0 },
        autoScrollEnabled: true,
        fileTree: null,
        fileTreeOpen: true,
        fileTreeOpenPaths: {},
        expandedEvents: {}, // Stores the expanded state of events

        init() {
            this.fetchSessions();
            this.fetchFileTree();
            setInterval(() => {
                this.fetchSessions();
                this.fetchFileTree();
            }, 5000);
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

        isFolder(path) {
            return this.fileTree && this.fileTree[path] && Object.keys(this.fileTree[path]).length > 0;
        },

        async fetchSessions() {
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                
                // Save expanded state from current session before replacing - use persistent storage
                const savedExpanded = {};
                if (this.currentSessionId) {
                    for (const [key, value] of Object.entries(this.expandedEvents)) {
                        if (key.startsWith(this.currentSessionId)) {
                            savedExpanded[key] = value;
                        }
                    }
                }
                
                this.activeSessions = data.active || {};
                this.historicalSessions = data.historical || {};
                
                // Update expandedEvents with saved state for current session
                if (this.currentSessionId) {
                    for (const key of Object.keys(savedExpanded)) {
                        this.expandedEvents[key] = savedExpanded[key];
                    }
                }
                
                // Restore expanded state to current session events
                if (this.currentSessionId && this.activeSessions[this.currentSessionId]?.events) {
                    const events = this.activeSessions[this.currentSessionId].events;
                    events.forEach((event, index) => {
                        const eventKey = `${this.currentSessionId}-${index}`;
                        if (savedExpanded.hasOwnProperty(eventKey)) {
                            event.expanded = savedExpanded[eventKey];
                        } else if (event.expanded === undefined) {
                            // Default: expand results, errors, tools, delegates; collapse thoughts
                            event.expanded = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
                            this.expandedEvents[eventKey] = event.expanded;
                        } else {
                            this.expandedEvents[eventKey] = event.expanded;
                        }
                    });
                    // Force Alpine.js reactivity by reassigning
                    this.activeSessions[this.currentSessionId].events = [...events];
                    this.currentSession = this.activeSessions[this.currentSessionId];
                }
            } catch(e) {
                console.log('Waiting for backend...');
            }
        },

        async startTask() {
            if (!this.newTaskInput.trim()) return;
            
            const task = this.newTaskInput;
            this.newTaskInput = '';

            try {
                await this.fetchSessions();
                
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
                    console.log('SSE event:', event);
                    
                    if (event.type === 'session_done') {
                        // Just update status locally - don't refetch everything!
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
                        
                        // Determine default expanded state - tools/delegate/results expanded, thoughts collapsed
                        const eventIndex = this.activeSessions[sessionId].events.length;
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
                console.log('SSE connection error, retrying...');
                this.eventSource.close();
                setTimeout(() => {
                    if (this.currentSessionId === sessionId && this.currentSession?.status === 'running') {
                        this.connectSSE(sessionId);
                    }
                }, 2000);
            };
        },

        async fetchSessionData(sessionId) {
            try {
                const res = await fetch(`/api/session/${sessionId}`);
                const data = await res.json();
                
                // Restore expanded state
                if (data.events) {
                    data.events.forEach((event, index) => {
                        const eventKey = `${sessionId}-${index}`;
                        if (this.expandedEvents.hasOwnProperty(eventKey)) {
                            event.expanded = this.expandedEvents[eventKey];
                        } else {
                            // Default state logic
                            event.expanded = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
                            this.expandedEvents[eventKey] = event.expanded;
                        }
                    });
                }
                
                this.activeSessions[sessionId] = data;
            } catch(e) {
                console.log('Error fetching session:', e);
            }
        },

        toggleEvent(sessionId, index) {
            const eventKey = `${sessionId}-${index}`;
            const currentState = this.expandedEvents[eventKey];
            // If undefined, use default logic to determine current state, then toggle
            const isExpanded = currentState !== undefined ? currentState : ['result', 'error', 'tool', 'delegate', 'system'].includes(this.currentSession?.events?.[index]?.type);
            
            this.expandedEvents[eventKey] = !isExpanded;
            
            // Update the event object directly to trigger reactivity
            if (this.currentSession && this.currentSession.events && this.currentSession.events[index]) {
                this.currentSession.events[index].expanded = !isExpanded;
                // Force Alpine.js reactivity by reassigning the events array
                this.currentSession.events = [...this.currentSession.events];
            }
        },

        get currentSession() {
            if (!this.currentSessionId) return null;
            return this.activeSessions[this.currentSessionId] || this.historicalSessions.find(s => s.id === this.currentSessionId);
        },

        get currentSessionEvents() {
            if (!this.currentSession || !this.currentSession.events) return [];
            return this.currentSession.events;
        },

        selectSession(id) {
            this.currentSessionId = id;
            this.connectSSE(id);
        },

        newChat() {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            this.currentSessionId = null;
            this._currentSession = null;
            this.newTaskInput = '';
        },

        async stopTask() {
            if (!this.currentSessionId) return;
            try {
                await fetch(`/api/session/${this.currentSessionId}/stop`, { method: 'POST' });
                this.fetchSessions();
            } catch(e) {}
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

        getCoordinatorEventType(type) {
            const types = {
                'coordinator_thinking': 'Анализ',
                'coordinator_decision': 'Решение',
                'planning_start': 'Планирование',
                'planning_complete': 'План готов',
                'coordinator_continue_check': 'Проверка',
                'coordinator_adjust_decision': 'Корректировка'
            };
            return types[type] || type;
        },
        
        getAgentDisplayName(agent) {
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
            return names[agent] || agent || 'Агент';
        },
        
        formatContent(content) {
            if (!content) return '';
            // Try to parse JSON and format nicely
            try {
                const json = JSON.parse(content);
                // If it has action/result, format as readable text
                if (json.action === 'done' && json.result) {
                    return json.result;
                }
                if (json.action === 'delegate' && json.agent && json.task) {
                    return `Делегирование: ${json.agent}\nЗадача: ${json.task}`;
                }
                if (json.action === 'tool' && json.tool) {
                    let text = `Инструмент: ${json.tool}`;
                    if (json.query) text += `\nЗапрос: ${json.query}`;
                    if (json.op) text += `\nОперация: ${json.op}`;
                    if (json.path) text += `\nПуть: ${json.path}`;
                    return text;
                }
                // Return formatted JSON for other cases
                return JSON.stringify(json, null, 2);
            } catch {
                // Not JSON, return as is
                return content;
            }
        },
        
        formatToolOutput(output, toolName) {
            if (!output) return '';
            
            // Format search results nicely
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
            
            // Console output - clean formatting
            if (toolName === 'console') {
                return '<pre class="console-output">' + this.escapeHtml(output) + '</pre>';
            }
            
            // Files tool
            if (toolName === 'files') {
                return '<pre class="files-output">' + this.escapeHtml(output) + '</pre>';
            }
            
            // Default: escape and preserve whitespace
            return '<pre class="text-xs font-mono">' + this.escapeHtml(output) + '</pre>';
        },
        
        buildSearchResultCard(num, title, source, body) {
            const bodyHtml = body.length > 0 
                ? '<div class="search-body">' + this.escapeHtml(body.join(' ')).substring(0, 300) + (body.join(' ').length > 300 ? '...' : '') + '</div>' 
                : '';
            const sourceHtml = source 
                ? `<a href="${this.escapeHtml(source)}" target="_blank" class="search-source">${this.escapeHtml(this.truncateUrl(source))} <i class="fas fa-external-link-alt"></i></a>` 
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
        
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        getAgentStyle(agent) {
            const styles = {
                'CriticAgent': { bg: 'bg-pink-50', border: 'border-pink-200', text: 'text-pink-700', icon: 'fa-glasses', iconColor: 'text-pink-600' },
                'SearchAgent': { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: 'fa-search', iconColor: 'text-blue-600' },
                'CodeAgent': { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', icon: 'fa-code', iconColor: 'text-green-600' },
                'Coordinator': { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', icon: 'fa-sitemap', iconColor: 'text-purple-600' }
            };
            const defaultStyle = { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-700', icon: 'fa-robot', iconColor: 'text-indigo-600' };
            return styles[agent] || defaultStyle;
        },

        scrollToBottom() {
            const el = document.getElementById('events-feed');
            if (el) {
                // Only scroll if we are already near the bottom or it's a new session
                const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
                if (isNearBottom || this.currentSessionEvents.length < 2) {
                    el.scrollTop = el.scrollHeight;
                }
            }
        }
    };
}
