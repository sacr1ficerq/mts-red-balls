const AUTO_EXPANDED_TYPES = new Set(['thought', 'result', 'error', 'delegate', 'system']);

function createMetrics() {
    return { total_tokens: 0, total_cost: 0 };
}

function getEventKey(sessionId, index) {
    return `${sessionId}-${index}`;
}

function shouldAutoExpand(type) {
    return AUTO_EXPANDED_TYPES.has(type);
}

function buildErrorEvent(message, agent = 'Coordinator', code = 'error') {
    return {
        type: 'error',
        agent,
        timestamp: new Date().toISOString(),
        data: {
            code,
            content: message
        }
    };
}

function cloneSteps(steps = []) {
    return steps.map((step) => ({ ...step }));
}

function parseEmbeddedJson(content) {
    if (typeof content !== 'string' || !content.includes('{')) {
        return null;
    }

    const direct = content.trim();
    try {
        return JSON.parse(direct);
    } catch (_error) {}

    const match = content.match(/\{[\s\S]*\}/);
    if (!match) {
        return null;
    }

    try {
        return JSON.parse(match[0]);
    } catch (_error) {
        return null;
    }
}

function buildPlanFromEvents(events = []) {
    let plan = null;

    for (const event of events) {
        if (event.type === 'plan' && Array.isArray(event.data?.steps)) {
            plan = {
                plan: event.data.plan || '',
                steps: cloneSteps(event.data.steps)
            };
            continue;
        }

        if (event.type === 'thought' && event.data?.content) {
            const parsed = parseEmbeddedJson(event.data.content);

            if (parsed?.plan && Array.isArray(parsed.steps)) {
                plan = {
                    plan: parsed.plan,
                    steps: cloneSteps(parsed.steps)
                };
                continue;
            }

            const update = parsed?.plan_update;
            if (plan && update?.step_id) {
                const step = plan.steps.find((item) => item.id === Number(update.step_id));
                if (step && update.status) {
                    step.status = update.status;
                }
            }
        }

        if (event.type === 'update_plan' && plan && event.data?.update?.step_id) {
            const step = plan.steps.find((item) => item.id === Number(event.data.update.step_id));
            if (step && event.data.update.status) {
                step.status = event.data.update.status;
            }
        }

        if (event.type === 'delegate' && plan && event.data?.step_id) {
            const step = plan.steps.find((item) => item.id === Number(event.data.step_id));
            if (step && step.status !== 'completed') {
                step.status = 'active';
            }
        }
    }

    return plan;
}

window.dashboard = function() {
    return {
        eventSource: null,
        sidebarOpen: true,
        newTaskInput: '',
        currentSessionId: null,
        activeSessions: {},
        historicalSessions: [],
        historicalSessionData: null,
        metrics: createMetrics(),
        fileTree: [],
        fileTreeOpen: true,
        fileTreeOpenPaths: {},
        sessionMetricsLoading: {},
        sessionMetricsPending: {},
        expandedEvents: {},
        currentPlan: null,
        error: null,

        // Settings state
        settingsOpen: false,
        settings: {
            api_key_masked: '',
            has_api_key: false,
            agent_models: {},
            default_model: 'openai/gpt-4o-mini'
        },
        availableModels: {
            free_models: [],
            all_models: []
        },
        newApiKey: '',
        settingsSaving: false,
        settingsError: null,
        settingsSuccess: null,

        init() {
            this.fetchSessions();
            this.loadSettings();
        },

        get currentSession() {
            if (!this.currentSessionId) {
                return null;
            }

            if (this.activeSessions[this.currentSessionId]) {
                return this.activeSessions[this.currentSessionId];
            }

            if (this.historicalSessionData?.id === this.currentSessionId) {
                return this.historicalSessionData;
            }

            return this.historicalSessions.find((session) => session.id === this.currentSessionId) || null;
        },

        get currentSessionEvents() {
            return this.currentSession?.events || [];
        },

        get sortedActiveSessions() {
            return Object.values(this.activeSessions)
                .filter((session) => session.created_at)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        },

        get sortedHistoricalSessions() {
            return [...this.historicalSessions]
                .filter((session) => session.created_at)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        },

        withExpandedState(sessionId, events = []) {
            return events.map((event, index) => {
                const key = getEventKey(sessionId, index);

                if (!(key in this.expandedEvents)) {
                    this.expandedEvents[key] = event.expanded ?? shouldAutoExpand(event.type);
                }

                return {
                    ...event,
                    expanded: this.expandedEvents[key]
                };
            });
        },

        normalizeSession(session, fallback = {}) {
            const normalized = {
                ...fallback,
                ...session
            };

            normalized.events = this.withExpandedState(normalized.id, normalized.events || []);
            return normalized;
        },

        syncMetrics(session) {
            if (!session) {
                this.metrics = createMetrics();
                return;
            }

            this.metrics = {
                total_tokens: session.total_tokens || 0,
                total_cost: session.total_cost || 0
            };
        },

        syncCurrentPlan() {
            this.currentPlan = buildPlanFromEvents(this.currentSessionEvents);
        },

        async refreshSessionMetrics(sessionId) {
            try {
                const latest = await API.fetchSessionData(sessionId);
                const activeSession = this.activeSessions[sessionId];

                if (!activeSession) {
                    return;
                }

                this.activeSessions = {
                    ...this.activeSessions,
                    [sessionId]: {
                        ...activeSession,
                        status: latest.status || activeSession.status,
                        total_tokens: latest.total_tokens || 0,
                        total_cost: latest.total_cost || 0
                    }
                };

                if (this.currentSessionId === sessionId) {
                    this.syncMetrics(this.activeSessions[sessionId]);
                }
            } catch (error) {
                console.error('Error refreshing session metrics:', error);
            }
        },

        scheduleMetricsRefresh(sessionId) {
            if (!sessionId) {
                return;
            }

            if (this.sessionMetricsLoading[sessionId]) {
                this.sessionMetricsPending[sessionId] = true;
                return;
            }

            this.sessionMetricsLoading[sessionId] = true;
            this.refreshSessionMetrics(sessionId)
                .finally(() => {
                    this.sessionMetricsLoading[sessionId] = false;

                    if (this.sessionMetricsPending[sessionId]) {
                        this.sessionMetricsPending[sessionId] = false;
                        this.scheduleMetricsRefresh(sessionId);
                    }
                });
        },

        closeEventSource() {
            if (!this.eventSource) {
                return;
            }

            this.eventSource.close();
            this.eventSource = null;
        },

        async fetchSessions() {
            try {
                const data = await API.fetchSessions();
                const nextActiveSessions = {};

                for (const session of Object.values(data.active || {})) {
                    nextActiveSessions[session.id] = this.normalizeSession(session);
                }

                this.activeSessions = nextActiveSessions;
                this.historicalSessions = data.historical || [];

                if (this.currentSessionId && this.activeSessions[this.currentSessionId]) {
                    this.syncMetrics(this.activeSessions[this.currentSessionId]);
                    this.syncCurrentPlan();
                }
            } catch (error) {
                console.error('Error fetching sessions:', error);
                this.error = 'Failed to load sessions';
            }
        },

        async fetchSessionData(sessionId) {
            try {
                const data = this.normalizeSession(await API.fetchSessionData(sessionId));

                if (this.historicalSessions.some((session) => session.id === sessionId)) {
                    this.historicalSessionData = data;
                } else {
                    this.activeSessions = {
                        ...this.activeSessions,
                        [sessionId]: data
                    };
                }

                if (this.currentSessionId === sessionId) {
                    this.syncMetrics(data);
                    this.syncCurrentPlan();
                }
            } catch (error) {
                console.error('Error fetching session:', error);
            }
        },

        createNewSession() {
            this.closeEventSource();
            this.currentSessionId = null;
            this.newTaskInput = '';
            this.historicalSessionData = null;
            this.currentPlan = null;
            this.metrics = createMetrics();
            this.fileTree = [];
        },

        async clearHistory() {
            if (!confirm('Очистить всю историю?')) {
                return;
            }

            try {
                await API.clearHistory();
                this.closeEventSource();
                this.activeSessions = {};
                this.historicalSessions = [];
                this.historicalSessionData = null;
                this.currentSessionId = null;
                this.currentPlan = null;
                this.metrics = createMetrics();
                this.fileTree = [];
            } catch (error) {
                console.error('Error clearing history:', error);
            }
        },

        async selectSession(id) {
            console.log('selectSession called with id:', id);
            this.currentSessionId = id;
            this.currentPlan = null;

            const session = this.activeSessions[id];
            console.log('Session from activeSessions:', session);
            if (session?.status === 'running') {
                this.syncMetrics(session);
                this.syncCurrentPlan();
                this.connectSSE(id);
            } else {
                console.log('Session not running or not in activeSessions, fetching session data');
                this.closeEventSource();
                await this.fetchSessionData(id);
            }

            // Refresh file tree for the selected session
            console.log('About to fetch file tree for session:', id);
            await this.fetchFileTree(id);
            console.log('File tree after fetch:', this.fileTree);
        },

        async stopSession() {
            if (!this.currentSessionId) {
                return;
            }

            try {
                await API.stopSession(this.currentSessionId);
                this.closeEventSource();
                await this.fetchSessions();
            } catch (error) {
                console.error('Error stopping session:', error);
            }
        },

        async selectOption(_event, option) {
            if (!this.currentSessionId) {
                return;
            }

            try {
                await API.selectOption(this.currentSessionId, option);
                await this.fetchSessions();
                await this.fetchSessionData(this.currentSessionId);
            } catch (error) {
                console.error('Error selecting option:', error);
            }
        },

        createPendingSession(task, sessionId) {
            return this.normalizeSession({
                id: sessionId,
                query: task,
                task,
                status: 'running',
                events: [
                    {
                        type: 'system',
                        data: { message: `Starting: ${task}` },
                        agent: 'Coordinator',
                        timestamp: new Date().toISOString()
                    }
                ],
                created_at: new Date().toISOString()
            });
        },

        buildFailedSession(task, sessionId, message, code = 'error') {
            return this.normalizeSession({
                id: sessionId,
                query: task,
                task,
                status: 'error',
                events: [buildErrorEvent(message, 'Coordinator', code)],
                created_at: new Date().toISOString()
            });
        },

        async startTask() {
            const task = this.newTaskInput.trim();
            if (!task) {
                return;
            }

            this.newTaskInput = '';

            const tempId = `temp-${Date.now()}`;
            this.currentSessionId = tempId;
            this.activeSessions = {
                ...this.activeSessions,
                [tempId]: this.createPendingSession(task, tempId)
            };
            this.syncMetrics(this.activeSessions[tempId]);
            this.syncCurrentPlan();

            try {
                const data = await API.startTask(task);
                const sessionId = data.session_id;
                const nextSession = this.normalizeSession({
                    id: sessionId,
                    query: task,
                    task,
                    status: data.status,
                    events: data.events || [],
                    created_at: new Date().toISOString(),
                    total_tokens: data.total_tokens || 0,
                    total_cost: data.total_cost || 0
                });

                const { [tempId]: _removed, ...rest } = this.activeSessions;
                this.activeSessions = {
                    ...rest,
                    [sessionId]: nextSession
                };
                this.currentSessionId = sessionId;
                this.syncMetrics(nextSession);
                this.syncCurrentPlan();

                if (data.status === 'running') {
                    this.connectSSE(sessionId);
                }
            } catch (error) {
                console.error('Error starting task:', error);
                const isRateLimit = error?.status === 429;
                const message = isRateLimit
                    ? (error.message || 'Rate limit exceeded. Please try again later.')
                    : (error?.message || 'Failed to start task. Please try again.');

                this.activeSessions[tempId] = this.buildFailedSession(
                    task,
                    tempId,
                    message,
                    isRateLimit ? 'rate_limit' : 'error'
                );
                this.syncMetrics(this.activeSessions[tempId]);
                this.syncCurrentPlan();
            }
        },

        isDuplicateEvent(events, nextEvent) {
            const nextData = JSON.stringify(nextEvent.data || null);
            return events.some((event) => (
                event.type === nextEvent.type &&
                event.timestamp === nextEvent.timestamp &&
                JSON.stringify(event.data || null) === nextData
            ));
        },

        appendEvent(sessionId, event) {
            const session = this.activeSessions[sessionId] || { id: sessionId, events: [], status: 'running' };
            const events = session.events || [];

            if (this.isDuplicateEvent(events, event)) {
                return;
            }

            const nextEvents = this.withExpandedState(sessionId, [...events, event]);
            const nextSession = {
                ...session,
                events: nextEvents
            };

            this.activeSessions = {
                ...this.activeSessions,
                [sessionId]: nextSession
            };

            if (this.currentSessionId === sessionId) {
                this.syncCurrentPlan();
                this.$nextTick(() => this.scrollToBottom());
                this.scheduleMetricsRefresh(sessionId);
                
                // Refresh file tree when file-related events occur
                if (event.type === 'tool' && event.data?.tool_name === 'files') {
                    this.fetchFileTree(sessionId);
                }
            }
        },

        connectSSE(sessionId) {
            this.closeEventSource();
            this.fetchSessionData(sessionId);

            const source = new EventSource(`/api/sse/${sessionId}`);
            this.eventSource = source;

            source.onmessage = (message) => {
                try {
                    const event = JSON.parse(message.data);

                    if (event.type === 'session_done') {
                        if (this.activeSessions[sessionId]) {
                            this.activeSessions[sessionId] = {
                                ...this.activeSessions[sessionId],
                                status: event.status || 'completed'
                            };
                        }
                        this.scheduleMetricsRefresh(sessionId);
                        return;
                    }

                    this.appendEvent(sessionId, event);
                } catch (error) {
                    console.error('SSE parse error:', error);
                }
            };

            source.onerror = () => {
                source.close();

                if (this.eventSource === source) {
                    this.eventSource = null;
                }

                const session = this.activeSessions[sessionId];
                if (this.currentSessionId === sessionId && session?.status === 'running') {
                    setTimeout(() => {
                        if (this.currentSessionId === sessionId && this.activeSessions[sessionId]?.status === 'running') {
                            this.connectSSE(sessionId);
                        }
                    }, 2000);
                }
            };
        },

        async fetchFileTree(sessionId = '') {
            try {
                console.log('=== fetchFileTree START ===');
                console.log('Fetching file tree for session:', sessionId);
                const data = await API.fetchFileTree(sessionId);
                console.log('File tree data:', data);
                console.log('Files from data:', data.files);
                console.log('Files length:', data.files ? data.files.length : 0);
                this.fileTree = data.files || [];
                console.log('File tree set to:', this.fileTree);
                console.log('File tree length:', this.fileTree.length);
                console.log('=== fetchFileTree END ===');
            } catch (error) {
                console.error('Error fetching files:', error);
                this.fileTree = [];
            }
        },

        async readFile(path) {
            try {
                const data = await API.readFile(path);
                return data.content || data.error || 'Пустой файл';
            } catch (_error) {
                return 'Ошибка чтения файла';
            }
        },

        toggleFolder(path) {
            if (this.fileTreeOpenPaths[path]) {
                delete this.fileTreeOpenPaths[path];
                return;
            }

            this.fileTreeOpenPaths[path] = true;
        },

        toggleEvent(sessionId, index) {
            const key = getEventKey(sessionId, index);
            const nextExpanded = !this.expandedEvents[key];
            this.expandedEvents[key] = nextExpanded;

            const session = this.currentSession;
            if (!session?.events?.[index]) {
                return;
            }

            session.events[index] = {
                ...session.events[index],
                expanded: nextExpanded
            };
            session.events = [...session.events];
        },

        scrollToBottom() {
            const element = document.getElementById('events-feed');
            if (!element) {
                return;
            }

            const isNearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 100;
            if (isNearBottom || this.currentSessionEvents.length < 2) {
                element.scrollTop = element.scrollHeight;
            }
        },

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

        getErrorStyle() {
            return Styles.getErrorStyle();
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
        },

        // Settings methods
        async loadSettings() {
            try {
                const [settingsData, modelsData] = await Promise.all([
                    window.API.getSettings(),
                    window.API.getAvailableModels()
                ]);
                this.settings = settingsData;
                this.availableModels = modelsData;
            } catch (err) {
                console.error('Failed to load settings:', err);
            }
        },

        openSettings() {
            this.settingsOpen = true;
            this.newApiKey = '';
            this.settingsError = null;
            this.settingsSuccess = null;
        },

        closeSettings() {
            this.settingsOpen = false;
            this.newApiKey = '';
            this.settingsError = null;
            this.settingsSuccess = null;
        },

        async saveApiKey() {
            if (!this.newApiKey.trim()) {
                this.settingsError = 'API key cannot be empty';
                return;
            }

            this.settingsSaving = true;
            this.settingsError = null;

            try {
                const result = await window.API.updateSettings({ api_key: this.newApiKey });
                this.settings = result;
                this.newApiKey = '';
                this.settingsSuccess = 'API key saved successfully';
                setTimeout(() => { this.settingsSuccess = null; }, 3000);
            } catch (err) {
                this.settingsError = err.message || 'Failed to save API key';
            } finally {
                this.settingsSaving = false;
            }
        },

        async updateAgentModel(agentName, model) {
            this.settingsSaving = true;
            this.settingsError = null;

            try {
                const result = await window.API.updateAgentSettings(agentName, { model });
                if (result.success) {
                    this.settings.agent_models[agentName] = {
                        model: result.model,
                        temperature: result.temperature,
                        max_tokens: result.max_tokens
                    };
                    this.settingsSuccess = `Model for ${agentName} updated`;
                    setTimeout(() => { this.settingsSuccess = null; }, 2000);
                }
            } catch (err) {
                this.settingsError = err.message || 'Failed to update model';
            } finally {
                this.settingsSaving = false;
            }
        },

        getAgentModel(agentName) {
            return this.settings.agent_models[agentName]?.model || this.settings.default_model;
        },

        getAllAgentNames() {
            return [
                'coordinator',
                'code',
                'search',
                'critic',
                'hypothesis',
                'data_preprocessor',
                'feature_engineer',
                'model_trainer',
                'data_parser',
                'kaggle_submitter'
            ];
        },

        formatAgentName(name) {
            return name.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
        }
    };
};
