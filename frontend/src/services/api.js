const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function request(url, options = {}) {
    const response = await fetch(url, options);
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
        const message = typeof payload === 'string'
            ? payload
            : payload?.error || payload?.message || payload?.detail || `Request failed: ${response.status}`;
        const error = new Error(message);
        error.status = response.status;
        error.payload = payload;
        throw error;
    }

    return payload;
}

window.API = {
    fetchSessions() {
        return request('/api/sessions');
    },

    fetchSessionData(sessionId) {
        return request(`/api/session/${sessionId}`);
    },

    startTask(task) {
        return request('/api/query', {
            method: 'POST',
            headers: JSON_HEADERS,
            body: JSON.stringify({ query: task })
        });
    },

    stopSession(sessionId) {
        return request(`/api/session/${sessionId}/stop`, { method: 'POST' });
    },

    clearHistory() {
        return request('/api/sessions/clear', { method: 'POST' });
    },

    selectOption(sessionId, option) {
        return request(`/api/session/${sessionId}/select`, {
            method: 'POST',
            headers: JSON_HEADERS,
            body: JSON.stringify({ selected: option })
        });
    },

    fetchFileTree(sessionId = '') {
        const url = sessionId
            ? `/api/workspace/files?session_id=${encodeURIComponent(sessionId)}`
            : '/api/workspace/files';
        return request(url);
    },

    readFile(path) {
        return request(`/api/workspace/read?path=${encodeURIComponent(path)}`);
    },

    // Settings API
    getSettings() {
        return request('/api/settings');
    },

    updateSettings(settings) {
        return request('/api/settings', {
            method: 'PUT',
            headers: JSON_HEADERS,
            body: JSON.stringify(settings)
        });
    },

    checkSettingsTokens(payload) {
        return request('/api/settings/check', {
            method: 'POST',
            headers: JSON_HEADERS,
            body: JSON.stringify(payload)
        });
    },

    getAvailableModels() {
        return request('/api/settings/models');
    },

    getAgentSettings(agentName) {
        return request(`/api/settings/agent/${encodeURIComponent(agentName)}`);
    },

    updateAgentSettings(agentName, config) {
        const params = new URLSearchParams();
        if (config.model) params.append('model', config.model);
        if (config.temperature !== undefined) params.append('temperature', config.temperature);
        if (config.max_tokens !== undefined) params.append('max_tokens', config.max_tokens);
        return request(`/api/settings/agent/${encodeURIComponent(agentName)}?${params.toString()}`, {
            method: 'PUT'
        });
    }
};
