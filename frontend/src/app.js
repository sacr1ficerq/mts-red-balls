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
                this.activeSessions = data.active || {};
                this.historicalSessions = data.historical || [];
                
                // Update current session if it's running
                if (this.currentSessionId && this.activeSessions[this.currentSessionId]) {
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
                // First fetch sessions to ensure we have the latest
                await this.fetchSessions();
                
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: task })
                });
                const data = await res.json();
                this.currentSessionId = data.session_id;
                
                // Fetch again to get the new session
                await this.fetchSessions();
                
                // Now connect SSE after session exists
                this.connectSSE(data.session_id);
            } catch(e) {
                console.error('Error starting task:', e);
            }
        },

        connectSSE(sessionId) {
            // Close existing connection
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            
            // First fetch session data directly
            this.fetchSessionData(sessionId);
            
            // Then connect to SSE for live updates
            this.eventSource = new EventSource(`/api/sse/${sessionId}`);
            
            this.eventSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    console.log('SSE event:', event);
                    
                    if (event.type === 'session_done') {
                        this.fetchSessions();
                        return;
                    }
                    
                    if (this.currentSessionId === sessionId) {
                        if (!this.activeSessions[sessionId]) {
                            this.activeSessions[sessionId] = { events: [], status: 'running' };
                        }
                        if (!this.activeSessions[sessionId].events) {
                            this.activeSessions[sessionId].events = [];
                        }
                        this.activeSessions[sessionId].events.push(event);
                        this.$nextTick(() => this.scrollToBottom());
                    }
                    
                    this.fetchSessions();
                } catch(err) {
                    console.error('SSE parse error:', err);
                }
            };
            
            this.eventSource.onerror = () => {
                console.log('SSE connection error, retrying...');
                this.eventSource.close();
                // Retry after a delay
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
                // Update the session in activeSessions
                this.activeSessions[sessionId] = data;
            } catch(e) {
                console.log('Error fetching session:', e);
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
            return new Date(timestamp).toLocaleTimeString();
        },

        formatDate(timestamp) {
            if (!timestamp) return '';
            return new Date(timestamp).toLocaleString();
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

        scrollToBottom() {
            const el = document.getElementById('events-feed');
            if (el) el.scrollTop = el.scrollHeight;
        }
    };
}
