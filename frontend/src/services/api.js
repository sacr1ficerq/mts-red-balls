const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function request(url, options = {}) {
    const response = await fetch(url, options);
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
        const message = typeof payload === 'string'
            ? payload
            : payload?.error || payload?.message || `Request failed: ${response.status}`;
        throw new Error(message);
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

    fetchFileTree() {
        return request('/api/workspace/files');
    },

    readFile(path) {
        return request(`/api/workspace/read?path=${encodeURIComponent(path)}`);
    }
};
