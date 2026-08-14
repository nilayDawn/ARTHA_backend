# 🧠 04. LangGraph Agent Workflow & Vector Memory

> **Stateful Agentic Reasoning & Qdrant Semantic Persistence**  
> *Detailed breakdown of the LangGraph multi-node state graph, structured JSON action blocks, and selective vector memory retrieval.*

---

## 📌 1. LangGraph State Machine Architecture

The ARTHA AI agent is designed around a **LangGraph StateGraph** state machine (`app/agent/graph.py`):

```
                     +---------------------------+
                     | security_guardrail_node   |
                     +-------------+-------------+
                                   |
                  +----------------+----------------+
                  |                                 |
           (is_blocked=True)                 (is_blocked=False)
                  |                                 |
                  v                                 v
                [END]                    +----------+----------+
                                         |   db_context_node   |
                                         +----------+----------+
                                                    |
                                                    v
                                         +----------+----------+
                                         | memory_recall_node  |
                                         +----------+----------+
                                                    |
                                                    v
                                         +----------+----------+
                                         | memory_save_node    |
                                         +----------+----------+
                                                    |
                                                    v
                                         +----------+----------+
                                         | llm_reasoning_node  |
                                         +----------+----------+
                                                    |
                                                    v
                                                  [END]
```

---

## 🛠 2. Node Responsibilities

1. **`security_guardrail_node`**: Validates input safety and domain relevance.
2. **`db_context_node`**: Retrieves user transactions, active budgets, and savings goals from TTL cache or Supabase.
3. **`memory_recall_node`**: Performs vector similarity search in Qdrant (`gemini-embedding-001`) scoped to `user_id`.
4. **`memory_save_node`**: Evaluates whether the user's input expresses a long-term rule/habit (`PREFERENCE_KEYWORDS`). Only important facts are embedded into Qdrant, avoiding database bloat.
5. **`llm_reasoning_node`**: Assembles compact context and generates actionable responses. Parses triple-backtick `json_action` blocks to automatically execute mutations in Supabase.

---

## ⚡ 3. Structured Action Block Execution Engine

When a user instructs the AI to add a financial goal, budget, or transaction, the LLM outputs a structured action block:

```json_action
{
  "action": "create_transaction",
  "data": {
    "amount": 500.0,
    "category": "Groceries",
    "merchant": "Supermarket"
  }
}
```

The backend parses this block, calls `create_user_transaction_in_db`, inserts the record into Supabase, and triggers automatic cache invalidation.
