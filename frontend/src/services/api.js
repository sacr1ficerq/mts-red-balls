// API service - all HTTP calls
window.API = {
    async fetchSessions() {
        const res = await fetch('/api/sessions');
        return res.json();
    },

    async fetchSessionData(sessionId) {
        const res = await fetch(`/api/session/${sessionId}`);
        return res.json();
    },

    async startTask(task) {
        console.log('Starting task:', task);
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: task })
        });
        console.log('Response status:', res.status);
        if (!res.ok) {
            const error = await res.text();
            console.error('API error:', error);
            throw new Error('Failed to start task: ' + error);
        }
        const data = await res.json();
        console.log('Response data:', data);
        return data;
    },

    async stopSession(sessionId) {
        await fetch(`/api/session/${sessionId}/stop`, { method: 'POST' });
    },

    async selectOption(sessionId, option) {
        await fetch(`/api/session/${sessionId}/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selected: option })
        });
    },

    async fetchFileTree() {
        const res = await fetch('/api/workspace/files');
        return res.json();
    },

    async readFile(path) {
        const res = await fetch(`/api/workspace/read?path=${encodeURIComponent(path)}`);
        return res.json();
    }
};
