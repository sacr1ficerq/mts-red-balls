// Main application - delegates to modules
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
                const data = await API.fetchSessions();
                console.log('[Sessions] Active:', Object.keys(data.active || {}).length, 'Historical:', (data.historical || []).length);
                
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
                console.error('[Sessions] Error:', e);
            }
        },

        async fetchSessionData(sessionId) {
            try {
                const data = await API.fetchSessionData(sessionId);
                
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
                await API.stopSession(this.currentSessionId);
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
                await this.fetchSessions();
            } catch(e) {
                console.error('Error stopping session:', e);
            }
        },

        async selectOption(event, option) {
            if (!this.currentSessionId) return;
            try {
                await API.selectOption(this.currentSessionId, option);
                await this.fetchSessions();
            } catch(e) {
                console.error('Error selecting option:', e);
            }
        },

        async startTask() {
            if (!this.newTaskInput.trim()) return;
            
            const task = this.newTaskInput;
            this.newTaskInput = '';
            
            try {
                const data = await API.startTask(task);
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
                const data = await API.fetchFileTree();
                this.fileTree = data.tree || {};
            } catch(e) {
                console.log('Error fetching files:', e);
            }
        },

        async readFile(path) {
            try {
                const data = await API.readFile(path);
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

        // Delegate to modules
        getAgentDisplayName(agent) {
            return Styles.getAgentDisplayName(agent);
        },

        getAgentIcon(agent) {
            return Styles.getAgentIcon(agent);
        },

        getAgentStyle(agent) {
            return Styles.getAgentStyle(agent);
        },

        getUserStyle() {
            return Styles.getUserStyle();
        },

        getToolStyle(toolName) {
            return Styles.getToolStyle(toolName);
        },

        getDelegateStyle() {
            return Styles.getDelegateStyle();
        },

        escapeHtml(text) {
            return Formatters.escapeHtml(text);
        },

        formatToolInput(input) {
            return Formatters.formatToolInput(input);
        },

        formatToolOutput(output, toolName) {
            return Formatters.formatToolOutput(output, toolName);
        },

        buildSearchResultCard(num, title, source, body) {
            return Formatters.buildSearchResultCard(num, title, source, body);
        },

        truncateUrl(url) {
            return Formatters.truncateUrl(url);
        },

        formatContent(content) {
            return Formatters.formatContent(content);
        }
    };
};
