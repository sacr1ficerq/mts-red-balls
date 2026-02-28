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
                
                const prevExpanded = {};
                
                // Save expanded state from current session before replacing
                if (this.currentSessionId && this.activeSessions[this.currentSessionId]?.events) {
                    this.activeSessions[this.currentSessionId].events.forEach((e, i) => {
                        if (e && e.expanded !== undefined) {
                            prevExpanded[i] = e.expanded;
                        }
                    });
                }
                
                this.activeSessions = data.active || {};
                this.historicalSessions = data.historical || [];
                
                // Restore expanded state to current session events
                if (this.currentSessionId && this.activeSessions[this.currentSessionId]?.events) {
                    const events = this.activeSessions[this.currentSessionId].events;
                    events.forEach((event, index) => {
                        if (prevExpanded.hasOwnProperty(index)) {
                            event.expanded = prevExpanded[index];
                        } else if (event.expanded === undefined) {
                            // Default: expand results, errors, tools, delegates; collapse thoughts
                            event.expanded = ['result', 'error', 'tool', 'delegate', 'system'].includes(event.type);
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
                        
                        // Determine default expanded state
                        const eventIndex = this.activeSessions[sessionId].events.length;
                        const eventKey = `${sessionId}-${eventIndex}`;
                        
                        if (!this.expandedEvents.hasOwnProperty(eventKey)) {
                            // Expand results, errors, tools, and delegates by default. Collapse thoughts.
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
