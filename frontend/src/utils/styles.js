// Style helpers - Agent styles configuration
// All agent styles are defined here in one place for easy maintenance

window.Styles = (function() {
    // Agent configuration - single source of truth
    const AGENT_CONFIG = {
        // Coordinator / Planner
        'Coordinator': { 
            name: 'Планировщик', 
            icon: 'fa-sitemap',
            colors: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', iconColor: 'text-blue-600', headerBg: 'bg-blue-50' }
        },
        'CoordinatorAgent': { extends: 'Coordinator' },
        
        // Code Agent / Programmer
        'CodeAgent': { 
            name: 'Программист', 
            icon: 'fa-code',
            colors: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', iconColor: 'text-green-600', headerBg: 'bg-green-50' }
        },
        'Code': { extends: 'CodeAgent' },
        
        // Search Agent
        'SearchAgent': { 
            name: 'Поисковик', 
            icon: 'fa-search',
            colors: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', iconColor: 'text-yellow-600', headerBg: 'bg-yellow-50' }
        },
        'Search': { extends: 'SearchAgent' },
        
        // Critic Agent
        'CriticAgent': { 
            name: 'Критик', 
            icon: 'fa-glasses',
            colors: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', iconColor: 'text-red-600', headerBg: 'bg-red-50' }
        },
        'Critic': { extends: 'CriticAgent' },
        
        // Creator Agent
        'CreatorAgent': { 
            name: 'Создатель', 
            icon: 'fa-pen',
            colors: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', iconColor: 'text-purple-600', headerBg: 'bg-purple-50' }
        },
        'Creator': { extends: 'CreatorAgent' },
        
        // Analyst
        'Analyst': { 
            name: 'Аналитик', 
            icon: 'fa-chart-line',
            colors: { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-700', iconColor: 'text-indigo-600', headerBg: 'bg-indigo-50' }
        }
    };

    // Resolve inheritance - get actual config for an agent
    function resolveConfig(agent) {
        const config = AGENT_CONFIG[agent];
        if (!config) return null;
        
        // Handle inheritance
        if (config.extends) {
            const parentConfig = resolveConfig(config.extends);
            if (parentConfig) {
                return {
                    name: config.name || parentConfig.name,
                    icon: config.icon || parentConfig.icon,
                    colors: { ...parentConfig.colors, ...config.colors }
                };
            }
        }
        return config;
    }

    return {
        // Get display name for agent
        getAgentDisplayName(agent) {
            if (!agent) return 'Агент';
            const config = resolveConfig(agent);
            return config ? config.name : agent;
        },

        // Get icon class for agent
        getAgentIcon(agent) {
            const config = resolveConfig(agent);
            return config ? config.icon : 'fa-robot';
        },

        // Get full style object for agent
        getAgentStyle(agent) {
            const config = resolveConfig(agent);
            if (config) {
                return {
                    ...config.colors,
                    icon: config.icon,
                    iconColor: config.colors.iconColor
                };
            }
            // Default style
            return { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-700', icon: 'fa-robot', iconColor: 'text-gray-600', headerBg: 'bg-gray-50' };
        },

        // User style (static)
        getUserStyle() {
            return { 
                icon: 'fa-user', 
                bg: 'bg-red-50', 
                border: 'border-red-200', 
                headerBg: 'bg-red-50', 
                text: 'text-red-700', 
                iconColor: 'text-red-600' 
            };
        },

        // Tool style (static)
        getToolStyle(toolName) {
            return {
                icon: toolName === 'search' ? 'fa-search' : toolName === 'console' ? 'fa-terminal' : 'fa-file-code',
                bg: 'bg-emerald-50', 
                border: 'border-emerald-200', 
                headerBg: 'bg-emerald-50', 
                text: 'text-emerald-700', 
                iconColor: 'text-emerald-600'
            };
        },

        // Delegate style (static)
        getDelegateStyle() {
            return { 
                icon: 'fa-share-alt', 
                bg: 'bg-purple-50', 
                border: 'border-purple-200', 
                headerBg: 'bg-purple-50', 
                text: 'text-purple-700', 
                iconColor: 'text-purple-600' 
            };
        },

        // Error style (static)
        getErrorStyle() {
            return { 
                icon: 'fa-triangle-exclamation', 
                bg: 'bg-red-50', 
                border: 'border-red-200', 
                headerBg: 'bg-red-50', 
                text: 'text-red-700', 
                iconColor: 'text-red-600', 
                bodyText: 'text-red-700' 
            };
        },

        // Helper to get all available agents (for debugging/settings)
        getAllAgents() {
            return Object.keys(AGENT_CONFIG).filter(k => !AGENT_CONFIG[k].extends);
        }
    };
})();
