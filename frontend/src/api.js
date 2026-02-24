/**
 * API module for backend communication
 */

const API_BASE = '/api';

export async function fetchSessions() {
    const res = await fetch(`${API_BASE}/sessions`);
    return res.json();
}

export async function startTask(query) {
    const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    });
    return res.json();
}

export async function getSession(sessionId) {
    const res = await fetch(`${API_BASE}/session/${sessionId}`);
    return res.json();
}

export async function stopSession(sessionId) {
    const res = await fetch(`${API_BASE}/session/${sessionId}/stop`, {
        method: 'POST'
    });
    return res.json();
}

export async function getTools() {
    const res = await fetch(`${API_BASE}/tools`);
    return res.json();
}

export function connectSSE(sessionId, onEvent, onDone) {
    const eventSource = new EventSource(`${API_BASE}/sse/${sessionId}`);
    
    eventSource.onmessage = (e) => {
        try {
            const event = JSON.parse(e.data);
            if (event.type === 'session_done') {
                onDone?.(event);
                eventSource.close();
                return;
            }
            onEvent?.(event);
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    };
    
    eventSource.onerror = () => {
        eventSource.close();
    };
    
    return eventSource;
}
