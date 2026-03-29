// Style helpers
window.Styles = {
    getAgentDisplayName(agent) {
        if (!agent) return 'Агент';
        const names = {
            'Coordinator': 'Планировщик', 'CoordinatorAgent': 'Планировщик',
            'CodeAgent': 'Программист', 'Code': 'Программист',
            'SearchAgent': 'Поисковик', 'Search': 'Поисковик',
            'CriticAgent': 'Критик', 'Critic': 'Критик',
            'CreatorAgent': 'Создатель', 'Creator': 'Создатель',
            'Analyst': 'Аналитик'
        };
        return names[agent] || agent;
    },

    getAgentIcon(agent) {
        const icons = {'Coordinator': 'fa-sitemap', 'CodeAgent': 'fa-code', 'SearchAgent': 'fa-search', 'CriticAgent': 'fa-glasses', 'Creator': 'fa-pen', 'Analyst': 'fa-chart-line'};
        return icons[agent] || 'fa-robot';
    },

    getAgentStyle(agent) {
        return { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: this.getAgentIcon(agent), iconColor: 'text-blue-600', headerBg: 'bg-blue-50' };
    },

    getUserStyle() {
        return { icon: 'fa-user', bg: 'bg-red-50', border: 'border-red-200', headerBg: 'bg-red-50', text: 'text-red-700', iconColor: 'text-red-600' };
    },

    getToolStyle(toolName) {
        return {
            icon: toolName === 'search' ? 'fa-search' : toolName === 'console' ? 'fa-terminal' : 'fa-file-code',
            bg: 'bg-emerald-50', border: 'border-emerald-200', headerBg: 'bg-emerald-50', text: 'text-emerald-700', iconColor: 'text-emerald-600'
        };
    },

    getDelegateStyle() {
        return { icon: 'fa-share-alt', bg: 'bg-purple-50', border: 'border-purple-200', headerBg: 'bg-purple-50', text: 'text-purple-700', iconColor: 'text-purple-600' };
    },

    getErrorStyle() {
        return { icon: 'fa-triangle-exclamation', bg: 'bg-red-50', border: 'border-red-200', headerBg: 'bg-red-50', text: 'text-red-700', iconColor: 'text-red-600', bodyText: 'text-red-700' };
    }
};
