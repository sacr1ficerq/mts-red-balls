<script>
// Legacy helpers - kept for compatibility
window.Helpers = {
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

    getStatusText(status) {
        const map = { 'running': 'В процессе', 'completed': 'Готово', 'cancelled': 'Прервано', 'error': 'Ошибка' };
        return map[status] || status;
    },

    getAgentIcon(agentName) {
        if (agentName?.includes('Coordinator')) return 'fa-chess-queen';
        if (agentName?.includes('Code')) return 'fa-code';
        if (agentName?.includes('Search')) return 'fa-search';
        if (agentName?.includes('Critic')) return 'fa-check-double';
        return 'fa-robot';
    },

    getEventTypeLabel(type) {
        const map = {
            'start': 'Начало', 'thinking': 'Размышление', 'thought': 'Мысль',
            'tool_start': 'Запуск инструмента', 'tool_end': 'Инструмент завершён',
            'delegate_start': 'Делегирование', 'delegate_end': 'Делегирование завершено',
            'done': 'Готово', 'error': 'Ошибка', 'token': 'Поток токенов'
        };
        return map[type] || type;
    }
};
</script>
