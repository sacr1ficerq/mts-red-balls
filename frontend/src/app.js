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
        metrics: { total_tokens: 0, total_cost: 0 },
        autoScrollEnabled: true,
        fileTree: null,
        fileTreeOpen: true,
        fileTreeOpenPaths: {},

        init() {
            this.fetchSessions();
            setInterval(() => this.fetchSessions(), 5000);
        },

        async fetchSessions() {
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                this.activeSessions = data.active || {};
                this.historicalSessions = data.historical || [];
            } catch(e) {
                console.log('Waiting for backend...');
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
                this.connectSSE(data.session_id);
                this.fetchSessions();
            } catch(e) {
                console.error('Error starting task:', e);
            }
        },

        connectSSE(sessionId) {
            if (this.eventSource) {
                this.eventSource.close();
            }
            
            this.eventSource = new EventSource(`/api/sse/${sessionId}`);
            
            this.eventSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    if (event.type === 'session_done') {
                        this.fetchSessions();
                        this.eventSource.close();
                        return;
                    }
                    
                    if (this.currentSessionId === sessionId && this.currentSession) {
                        if (!this.currentSession.events) {
                            this.currentSession.events = [];
                        }
                        this.currentSession.events.push(event);
                    }
                    
                    this.fetchSessions();
                } catch(err) {
                    console.error('SSE parse error:', err);
                }
            };
            
            this.eventSource.onerror = () => {
                this.eventSource.close();
            };
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
