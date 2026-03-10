# Полный отчет о проблемах в системе Multi-Agent Kaggle Solver

## КРИТИЧЕСКИЕ БАГИ (System Breaking)

### 1. Неправильный импорт в orchestrator.py
**Файл:** `backend/kaggle_solver/core/orchestrator.py:12`
```python
from kaggle_solver.tools import console_tool, files_tool, search_tool
```
**Проблема:** Эти функции не экспортируются из `kaggle_solver.tools.__init__.py`
**Влияние:** Система не запускается - ImportError при импорте orchestrator
**Статус:** СИСТЕМА НЕ РАБОТАЕТ

---

### 2. Контекст session не передается правильно в run()
**Файл:** `backend/kaggle_solver/core/orchestrator.py:165`
```python
result = coordinator.run(query, {"session_id": session.id})
```
**Проблема:** Передается session_id (строка), но не session object
**Также:** `backend/server.py:339` - аналогичная проблема
**Влияние:** Агент не получает доступ к session для подписки на события

---

### 3. agent_factory_fn не передает event_callback
**Файл:** `backend/kaggle_solver/core/orchestrator.py:71-76`
```python
def agent_factory_fn(**kwargs):
    agent_name = kwargs.get("name", "")
    agent_role = kwargs.get("role", "")
    agent_tools = kwargs.get("tools", ["tool"])
    return self.create_agent(agent_name, agent_role, agent_tools, event_callback, None, sandbox, session)
```
**Проблема:** `event_callback=None` вместо `event_callback=event_callback` (строка 75)
**Влияние:** Sub-agents не получают event_callback, события не логируются

---

## БАГИ ДЕЛЕГИРОВАНИЯ

### 4. Sub-agents создаются с неправильными tools
**Файл:** `backend/kaggle_solver/agents/base.py:232, 303, 329`
```python
sub = self.agent_factory(name="SearchAgent", ..., tools=["tool"])
sub = self.agent_factory(name=target, ..., tools=["tool"])
critic = self.agent_factory(name="CriticAgent", ..., tools=["tool"])
```
**Проблема:** Все sub-агенты создаются с `tools=["tool"]` вместо правильных инструментов
- SearchAgent должен иметь: `tools=["search"]`
- CodeAgent должен иметь: `tools=["console", "files"]`
- CriticAgent должен иметь: `tools=["search", "console"]`

**Влияние:** Sub-agents не могут выполнять свои задачи

---

### 5. Forced delegation всегда вызывает SearchAgent
**Файл:** `backend/kaggle_solver/agents/base.py:232`
```python
sub = self.agent_factory(name="SearchAgent", ...)
```
**Проблема:** После 2 последовательных планов, система всегда вызывает SearchAgent, даже если нуж CodeAgent
**Влияние:** Неправильный агент выполняет задачу

---

### 6. agent_factory не передается в AgentRegistry.create()
**Файл:** `backend/kaggle_solver/core/orchestrator.py:93-95`
```python
return AgentRegistry.create(
    name, agent_config, self.llm, current_sandbox, self.tool_registry, event_callback, agent_factory, session
)
```
**Проблема:** agent_factory передается, но...
**Файл:** `backend/kaggle_solver/agents/registry.py:24-34`
```python
def create(cls, name, config, llm, sandbox, tool_registry, 
           event_callback: Optional[Callable] = None,
           agent_factory: Optional[Callable] = None,
           session: Optional[Any] = None):
```
**Но в base.py при создании sub-agent (строка 303):**
```python
sub = self.agent_factory(name=target, ...)
```
**Проблема:** self.agent_factory может быть None для sub-agents, созданных через AgentRegistry
**Влияние:** Sub-agents не могут создавать свои собственные sub-sub-agents

---

## ПРОБЛЕМЫ С ПРОМПТАМИ

### 7. Missing delegate.yaml
**Файл:** `backend/kaggle_solver/prompts/tools/delegate.yaml` - НЕ СУЩЕСТВУЕТ
**Проблема:** Coordinator использует `{delegate_tool}` placeholder, но файла нет
**Решение работает через:** plan.yaml содержит delegate_tool, но это неправильная архитектура

---

### 8. Missing update_plan.yaml
**Файл:** `backend/kaggle_solver/prompts/tools/update_plan.yaml` - НЕ СУЩЕСТВУЕТ
**Аналогично:** Содержимое в plan.yaml

---

### 9. Undefined {rule_tools} в search.yaml
**Файл:** `backend/kaggle_solver/prompts/search.yaml:8`
```yaml
Tools:
{rule_tools}
```
**Проблема:** `{rule_tools}` не определен ни в одном YAML файле
**Влияние:** Промпт содержит необработанный placeholder

---

### 10. CriticAgent не имеет доступа к console/files
**Файл:** `backend/kaggle_solver/prompts/critic.yaml:7-8`
```yaml
{search_tool}
{result_tool}
```
**Проблема:** CriticAgent не может выполнять код для проверки
**Также:** config.yaml:63 - CriticAgent имеет tools: ["message", "search", "console"], но промпт не включает console_tool

---

## ПРОБЛЕМЫ С КОНТЕКСТОМ

### 11. Ограничение на 3 контекстных события
**Файл:** `backend/kaggle_solver/agents/base.py:82, 171`
```python
MAX_CONTEXT_EVENTS = 3
event_ids = context["event_ids"][:self.MAX_CONTEXT_EVENTS]
```
**Проблема:** Sub-agents получают максимум 3 события из контекста
**Влияние:** Потеря важного контекста при сложных任务ах

---

### 12. session передается через конструктор, но не через context
**Файл:** `backend/kaggle_solver/agents/base.py:165-167`
```python
if "session" in context:
    self.session = context["session"]
```
**Проблема:** В run() проверяется session в context, но в orchestrator session передается через конструктор
**Влияние:** Непоследовательное поведение

---

## ДРУГИЕ ПРОБЛЕМЫ

### 13. Mock LLM по умолчанию
**Файл:** `backend/kaggle_solver/llm.py:28-30`
```python
if not self.api_key:
    logger.warning("No API key found for LLM. Using mock mode.")
    self.client = None
```
**Проблема:** Если нет API ключа, система работает в mock режиме и всегда возвращает mock ответы
**Влияние:** Система выглядит как работает, но не выполняет реальные задачи

---

### 14. tools в AgentConfig не используется
**Файл:** `backend/kaggle_solver/agents/base.py:101-110`
```python
def __init__(self, config: AgentConfig, ...):
    self.config = config
    ...
```
**Проблема:** tools из AgentConfig сохраняются, но не используются для проверки/фильтрации
**Влияние:** Агент может пытаться использовать неразрешенные инструменты

---

### 15. CriticAgent вызывается после каждого delegate
**Файл:** `backend/kaggle_solver/agents/base.py:327-341`
```python
if self.agent_factory and sub_result.output:
    critic = self.agent_factory(...)
```
**Проблема:** CriticAgent запускается автоматически после каждого delegate, даже если не нужен
**Влияние:** Дополнительные затраты на LLM вызовы, возможные проблемы с итерациями

---

## СВОДКА

| # | Проблема | Критичность | Файл:строка |
|---|----------|-------------|-------------|
| 1 | Неправильный импорт | КРИТИЧЕСКАЯ | orchestrator.py:12 |
| 2 | session не передается в run() | КРИТИЧЕСКАЯ | orchestrator.py:165 |
| 3 | event_callback=None в factory | КРИТИЧЕСКАЯ | orchestrator.py:75 |
| 4 | Sub-agents с tools=["tool"] | КРИТИЧЕСКАЯ | base.py:232,303,329 |
| 5 | Forced delegation -> SearchAgent | КРИТИЧЕСКАЯ | base.py:232 |
| 6 | agent_factory не работает | КРИТИЧЕСКАЯ | registry.py |
| 7 | Missing delegate.yaml | ВЫСОКАЯ | - |
| 8 | Missing update_plan.yaml | ВЫСОКАЯ | - |
| 9 | {rule_tools} undefined | ВЫСОКАЯ | search.yaml:8 |
| 10 | CriticAgent без console | СРЕДНЯЯ | critic.yaml |
| 11 | MAX_CONTEXT_EVENTS = 3 | СРЕДНЯЯ | base.py:82 |
| 12 | session в конструкторе vs context | СРЕДНЯЯ | base.py:165 |
| 13 | Mock LLM по умолчанию | СРЕДНЯЯ | llm.py:28 |
| 14 | tools не используется | НИЗКАЯ | base.py |
| 15 | CriticAgent после delegate | НИЗКАЯ | base.py:327 |

---

## РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ

### Приоритет 1 (Система не работает):
1. Исправить импорт в orchestrator.py (убрать неиспользуемый импорт)
2. Исправить agent_factory_fn для передачи event_callback
3. Исправить создание sub-agents с правильными tools

### Приоритет 2 (Делегирование не работает):
4. Исправить передачу session в run() контекст
5. Добавить agent_factory для sub-agents
6. Исправить forced delegation логику

### Приоритет 3 (Промпты):
7. Создать delegate.yaml
8. Создать update_plan.yaml
9. Удалить {rule_tools} из search.yaml
10. Добавить console_tool в CriticAgent промпт

### Приоритет 4 (Улучшения):
11. Увеличить MAX_CONTEXT_EVENTS
12. Добавить проверку tools в AgentConfig
13. Сделать CriticAgent опциональным
