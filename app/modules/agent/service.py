import datetime
import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.modules.agent.state import AgentState
from app.modules.finance.service import (
    BudgetService,
    GoalService,
    TransactionService,
)
from app.ports.cache import CachePort
from app.ports.database import (
    BudgetRepositoryPort,
    GoalRepositoryPort,
    TransactionRepositoryPort,
)
from app.ports.llm import LLMProviderPort
from app.ports.vector_store import VectorStorePort
from app.utils.logger import logger

UNETHICAL_OR_BLOCKED_KEYWORDS = [
    "ignore previous instructions",
    "jailbreak",
    "override safety",
    "dan mode",
    "act as a unrestricted",
    "bypass restrictions",
    "forget rules",
]

FINANCIAL_INTENT_KEYWORDS = [
    "spent", "spend", "bought", "buy", "income", "salary", "deposit",
    "budget", "goal", "save", "savings", "balance", "cost", "expense",
    "transaction", "report", "money", "rupee", "cash", "invest", "bill",
    "pay", "paid", "food", "travel", "uber", "swiggy", "zomato", "amazon",
]

PREFERENCE_KEYWORDS = [
    "prefer", "habit", "usually", "always", "salary", "income",
    "paycheck", "monthly limit", "save for", "saving for", "never spend",
    "my goal", "favorite", "allot",
]

DEFAULT_REFUSAL_MESSAGE = (
    "I am your dedicated ARTHA AI Financial Assistant. "
    "I can help you assist with personal finance, budgeting, spending analysis, "
    "and financial goals. Please ask me a financial query!"
)


class MemoryService:
    """
    Domain service for semantic vector memory.
    Manages user financial preferences and habits.
    """

    def __init__(self, vector_store: VectorStorePort, llm_provider: LLMProviderPort):
        self.vector_store = vector_store
        self.llm = llm_provider

    def save_memory(self, user_id: str, memory_text: str, category: str = "general") -> bool:
        try:
            vector = self.llm.generate_embedding(memory_text)
            return self.vector_store.upsert_memory(user_id, memory_text, category, vector)
        except Exception as e:
            logger.error("[MemoryService Save Error]: %s", e)
            return False

    def search_memories(self, user_id: str, query: str, limit: int = 3) -> list[str]:
        try:
            query_vector = self.llm.generate_embedding(query)
            return self.vector_store.search_memories(user_id, query_vector, limit=limit)
        except Exception as e:
            logger.error("[MemoryService Search Error]: %s", e)
            return []


class AIAgentService:
    """
    Core AI CFO Agent Service powered by LangGraph and Gemini.
    Features fast-path heuristic guardrails to eliminate double-LLM latency,
    compact context formatting, and structured multi-action execution.
    """

    def __init__(
        self,
        llm: LLMProviderPort,
        memory_service: MemoryService,
        tx_service: TransactionService,
        budget_service: BudgetService,
        goal_service: GoalService,
        tx_repo: TransactionRepositoryPort,
        budget_repo: BudgetRepositoryPort,
        goal_repo: GoalRepositoryPort,
        cache: CachePort,
    ):
        self.llm = llm
        self.memory_service = memory_service
        self.tx_service = tx_service
        self.budget_service = budget_service
        self.goal_service = goal_service
        self.tx_repo = tx_repo
        self.budget_repo = budget_repo
        self.goal_repo = goal_repo
        self.cache = cache
        self.graph = self._build_graph()

    def evaluate_guardrail(self, query: str, custom_api_key: str | None = None) -> tuple[bool, str]:
        if not query or not query.strip():
            return True, "Empty message provided. Please enter a valid financial question."

        lower_query = query.lower()

        # 1. Immediate Injection / Exploit Block
        for kw in UNETHICAL_OR_BLOCKED_KEYWORDS:
            if kw in lower_query:
                return True, "I am your dedicated ARTHA AI Financial Assistant. I cannot process prompt injections or unauthorized system commands."

        # 2. Fast-path intent bypass: 90% of valid queries pass with 0 latency
        if any(kw in lower_query for kw in FINANCIAL_INTENT_KEYWORDS):
            return False, ""

        # 3. Only if query is ambiguous, invoke lightweight domain classification
        try:
            classification_prompt = (
                "You are a strict security and domain filter for a Personal Finance AI named ARTHA. "
                "Classify this query: ALLOW if related to personal finance, money, budgets, spending, income, goals, taxes, receipts; "
                "or BLOCK if completely unrelated (coding, trivia, weather) or harmful.\n"
                f'User Query: "{query}"\n'
                'Respond strictly in valid JSON: {"decision": "ALLOW"} or {"decision": "BLOCK"}'
            )
            raw = self.llm.generate_text(classification_prompt, custom_api_key=custom_api_key)
            text = (raw or "").strip()
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()
            data = json.loads(text)
            if data.get("decision") == "BLOCK":
                return True, DEFAULT_REFUSAL_MESSAGE
        except Exception as e:
            logger.warning("[Guardrail Fallback]: %s", e)

        return False, ""

    def fetch_compact_context(self, user_id: str) -> str:
        cache_key = f"user_financial_context:{user_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        txs = self.tx_repo.get_transactions(user_id=user_id, limit=10)
        budgets = self.budget_repo.get_budgets(user_id=user_id)
        goals = self.goal_repo.get_goals(user_id=user_id)

        tx_summary = ", ".join([f"₹{t.get('amount')}({t.get('category')}/{t.get('merchant')},{t.get('date')})" for t in txs]) or "None"
        budget_summary = ", ".join([f"{b.get('category')}:₹{b.get('monthly_limit')}/mo" for b in budgets]) or "None"
        goal_summary = ", ".join([f"{g.get('goal_name')}:₹{g.get('saved_amount')}/₹{g.get('target_amount')}" for g in goals]) or "None"

        compact = f"Tx: [{tx_summary}] | Budgets: [{budget_summary}] | Goals: [{goal_summary}]"
        self.cache.set(cache_key, compact, ttl_seconds=180)
        return compact

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        def guardrail_node(state: AgentState):
            user_msg = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                    break
            is_blocked, refusal = self.evaluate_guardrail(user_msg, state.get("custom_api_key"))
            if is_blocked:
                return {"is_blocked": True, "messages": [AIMessage(content=refusal)]}
            return {"is_blocked": False}

        def route_guardrail(state: AgentState):
            return END if state.get("is_blocked") else "fetch_context"

        def context_node(state: AgentState):
            user_id = state["user_id"]
            compact = self.fetch_compact_context(user_id)
            return {"db_context": {"summary": compact}}

        def memory_recall_node(state: AgentState):
            user_id = state["user_id"]
            user_msg = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                    break
            memories = self.memory_service.search_memories(user_id, user_msg) if user_msg else []
            return {"memories": memories}

        def reasoning_node(state: AgentState):
            user_id = state["user_id"]
            today = datetime.date.today()
            today_str = today.isoformat()
            yesterday_str = (today - datetime.timedelta(days=1)).isoformat()
            compact_summary = state.get("db_context", {}).get("summary", "")

            system_prompt = f"""
            You are ARTHA AI, a dedicated, knowledgeable, and sharp personal AI financial assistant.
            Current User Context:
            - User ID: {user_id}
            - Today's Date: {today_str}
            - Yesterday's Date: {yesterday_str}
            - Financial Data Summary: {compact_summary}
            - Long-Term Memories: {json.dumps(state.get('memories', []))}
            
            Guidelines:
            1. Provide precise, actionable financial insights grounded in user data.
            2. ACTION EXECUTION:
               If user asks to ADD, CREATE, SET, or LOG financial goals, transactions, or budgets:
               Append JSON action block at the END tagged ```json_action ... ```.
               Format:
               ```json_action
               {{"action": "create_transaction", "data": {{"amount": 500.0, "category": "Groceries", "merchant": "Supermarket", "date": "{today_str}"}}}}
               ```
               ```json_action
               {{"action": "create_goal", "data": {{"goal_name": "Laptop", "target_amount": 80000.0}}}}
               ```
               ```json_action
               {{"action": "create_budget", "data": {{"category": "Food", "monthly_limit": 15000.0}}}}
               ```
            """

            formatted_contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
            for msg in state.get("messages", []):
                role = "user" if isinstance(msg, HumanMessage) else "model"
                formatted_contents.append({"role": role, "parts": [{"text": msg.content}]})

            reply = self.llm.generate_text(
                formatted_contents,
                custom_api_key=state.get("custom_api_key"),
            ) or "I was unable to analyze your financial query at this time."

            # Parse and execute structured action blocks
            if "```json_action" in reply:
                pattern = r"```json_action\s*([\s\S]*?)\s*```"
                matches = re.findall(pattern, reply)
                for action_str in matches:
                    try:
                        action_data = json.loads(action_str.strip())
                        actions_list = action_data if isinstance(action_data, list) else [action_data]
                        for item in actions_list:
                            act = item.get("action")
                            data = item.get("data", {})
                            if act == "create_transaction":
                                self.tx_service.create_transaction(user_id, data)
                                self.memory_service.save_memory(
                                    user_id,
                                    f"Logged transaction ₹{data.get('amount')} ({data.get('category')}/{data.get('merchant')})",
                                    "transaction",
                                )
                            elif act == "create_budget":
                                self.budget_service.create_budget(user_id, data)
                                self.memory_service.save_memory(
                                    user_id,
                                    f"Set budget ₹{data.get('monthly_limit')} for {data.get('category')}",
                                    "budget",
                                )
                            elif act == "create_goal":
                                self.goal_service.create_goal(user_id, data)
                                self.memory_service.save_memory(
                                    user_id,
                                    f"Created goal '{data.get('goal_name')}' target ₹{data.get('target_amount')}",
                                    "goal",
                                )
                    except Exception as e:
                        logger.warning("[Action Execution Error]: %s", e)

                reply = re.sub(pattern, "", reply).strip()

            return {"messages": [AIMessage(content=reply)]}

        def memory_save_node(state: AgentState):
            user_id = state["user_id"]
            user_msg = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                    break
            if user_msg and len(user_msg.strip()) >= 15:
                lower = user_msg.lower()
                if any(kw in lower for kw in PREFERENCE_KEYWORDS):
                    self.memory_service.save_memory(user_id, user_msg.strip(), "preference")
            return {}

        workflow.add_node("guardrail", guardrail_node)
        workflow.add_node("fetch_context", context_node)
        workflow.add_node("recall_memory", memory_recall_node)
        workflow.add_node("reasoning", reasoning_node)
        workflow.add_node("save_memory", memory_save_node)

        workflow.set_entry_point("guardrail")
        workflow.add_conditional_edges("guardrail", route_guardrail, {END: END, "fetch_context": "fetch_context"})
        workflow.add_edge("fetch_context", "recall_memory")
        workflow.add_edge("recall_memory", "reasoning")
        workflow.add_edge("reasoning", "save_memory")
        workflow.add_edge("save_memory", END)

        return workflow.compile()

    def process_chat(
        self,
        user_id: str,
        message: str,
        history: list[dict[str, str]] | None = None,
        custom_api_key: str | None = None,
    ) -> dict[str, Any]:
        messages = []
        for h in history or []:
            if h.get("role") == "user":
                messages.append(HumanMessage(content=h.get("content", "")))
            elif h.get("role") == "assistant":
                messages.append(AIMessage(content=h.get("content", "")))

        messages.append(HumanMessage(content=message))

        initial_state = {
            "messages": messages,
            "user_id": user_id,
            "custom_api_key": custom_api_key,
            "memories": [],
            "db_context": {},
        }

        final_state = self.graph.invoke(initial_state)
        last_msg = final_state["messages"][-1]
        text_content = last_msg.content if isinstance(last_msg, AIMessage) else str(last_msg)

        return {
            "response": text_content,
            "memories_used": final_state.get("memories", []),
        }
