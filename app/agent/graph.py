import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agent.guardrail import evaluate_security_guardrail
from app.agent.state import AgentState
from app.agent.tools import (
    create_user_budget_in_db,
    create_user_goal_in_db,
    create_user_transaction_in_db,
    fetch_relevant_memories,
    fetch_user_financial_context,
    remember_user_preference,
)
from app.core.llm_setup import generate_with_fallback
from app.utils.logger import logger


def security_guardrail_node(state: AgentState) -> dict[str, Any]:
    """
    Entry Guardrail Node: Evaluates user query before any DB or Memory fetch.
    Blocks irrelevant, out-of-scope, unethical, or prompt injection queries.
    """
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    logger.info("[AGENT GUARDRAIL] Evaluating input message for UserID: %s", state.get("user_id"))
    is_blocked, refusal_message = evaluate_security_guardrail(last_user_msg)

    if is_blocked:
        logger.warning("[AGENT GUARDRAIL] Query blocked for UserID: %s | Refusal: %s", state.get("user_id"), refusal_message)
        return {
            "is_blocked": True,
            "messages": [AIMessage(content=refusal_message)],
        }

    logger.info("[AGENT GUARDRAIL] Query passed for UserID: %s", state.get("user_id"))
    return {"is_blocked": False}


def route_after_guardrail(state: AgentState) -> str:
    """
    Conditional Edge Router:
    If blocked by security guardrail, immediately terminate graph execution.
    Otherwise, proceed to database context retrieval.
    """
    if state.get("is_blocked"):
        logger.info("[AGENT ROUTER] Short-circuiting execution to END due to security guardrail block.")
        return END
    return "fetch_db_context"


def db_context_node(state: AgentState) -> dict[str, Any]:
    """Node: Pulls recent transactions, budgets, and goals from Supabase."""
    user_id = state["user_id"]
    logger.info("[AGENT DB NODE] Fetching financial context for UserID: %s", user_id)
    context = fetch_user_financial_context(user_id)
    return {"db_context": context}


def memory_recall_node(state: AgentState) -> dict[str, Any]:
    """Node: Retrieves contextual long-term user memories and user preferences from Qdrant."""
    user_id = state["user_id"]
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    logger.info("[AGENT MEMORY NODE] Recalling vector memories for UserID: %s", user_id)
    memories = fetch_relevant_memories(user_id, last_user_msg) if last_user_msg else []
    logger.info("[AGENT MEMORY NODE] Retrieved %d memory records.", len(memories))
    return {"memories": memories}


PREFERENCE_KEYWORDS = [
    "prefer", "habit", "usually", "always", "salary", "income",
    "paycheck", "monthly limit", "save for", "saving for", "never spend",
    "my goal", "favorite", "allot"
]


def memory_save_node(state: AgentState) -> dict[str, Any]:
    """Node: Selectively saves ONLY important financial preferences and habits to Qdrant."""
    user_id = state["user_id"]
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg or len(last_user_msg.strip()) < 15:
        logger.debug("[MEMORY SAVE NODE] Skipping save for short/empty query.")
        return {"user_preferences": []}

    # Only save if message expresses a long-term preference/habit
    lower_msg = last_user_msg.lower()
    is_important = any(kw in lower_msg for kw in PREFERENCE_KEYWORDS)

    if is_important:
        logger.info("[MEMORY SAVE NODE] Saving user preference to Qdrant for UserID: %s", user_id)
        remember_user_preference(user_id, last_user_msg.strip(), category="preference")
        return {"user_preferences": [last_user_msg]}

    logger.info("[MEMORY SAVE NODE] Message classified as generic chat. Skipped Qdrant persistence.")
    return {"user_preferences": []}


def llm_reasoning_node(state: AgentState) -> dict[str, Any]:
    """Node: Generates response using Gemini Flash and executes database mutation actions."""
    from app.agent.tools import format_compact_financial_context
    import datetime

    today_dt = datetime.date.today()
    today_str = today_dt.isoformat()
    yesterday_str = (today_dt - datetime.timedelta(days=1)).isoformat()

    compact_db_summary = format_compact_financial_context(state.get("db_context", {}))
    
    system_prompt = f"""
    You are ARTHA AI, a dedicated, knowledgeable, and sharp personal AI financial employee.
    
    Current User Context:
    - User ID: {state['user_id']}
    - Today's Date: {today_str}
    - Yesterday's Date: {yesterday_str}
    - Financial Data Summary: {compact_db_summary}
    - Long-Term Memories: {json.dumps(state.get('memories', []))}
    
    Guidelines:
    1. Provide precise, actionable financial insights based on the user's data.
    2. Ground your response strictly using the provided financial context.
    3. Keep answers conversational, helpful, concise, and easy to read using markdown formatting.
    4. ACTION EXECUTION:
       If the user asks you to ADD, CREATE, SET, or LOG new financial goals, transactions, or budgets:
       You MUST append a JSON action block at the VERY END of your text inside triple backticks tagged ```json_action ... ```.
       If the user asks to add MULTIPLE transactions (e.g. an expense AND an income/bonus), output a separate ```json_action ... ``` block for EACH item.
       ALWAYS include a "date" parameter in YYYY-MM-DD format based on relative timing mentioned (e.g., if user says "yesterday", set date to "{yesterday_str}"; if "today", set date to "{today_str}").

       - Goal Creation Format:
       ```json_action
       {{"action": "create_goal", "data": {{"goal_name": "Laptop", "target_amount": 82000.0, "saved_amount": 0.0}}}}
       ```

       - Transaction Creation Format (For Income/Bonus, set category to "Income"; set exact date YYYY-MM-DD):
       ```json_action
       {{"action": "create_transaction", "data": {{"amount": 500.0, "category": "Groceries", "merchant": "Supermarket", "date": "{today_str}"}}}}
       ```
       ```json_action
       {{"action": "create_transaction", "data": {{"amount": 200.0, "category": "Income", "merchant": "Work Bonus", "date": "{yesterday_str}"}}}}
       ```

       - Budget Creation Format:
       ```json_action
       {{"action": "create_budget", "data": {{"category": "Food", "monthly_limit": 15000.0}}}}
       ```
    """

    # Prepare message history
    formatted_contents = [{"role": "user", "parts": [{"text": system_prompt}]}]

    for msg in state["messages"]:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        formatted_contents.append({"role": role, "parts": [{"text": msg.content}]})

    response = generate_with_fallback(formatted_contents)

    reply = response or "I was unable to analyze your financial query at this time."

    # Parse and execute ALL structured action blocks (e.g. multiple transactions, goals, budgets)
    if "```json_action" in reply:
        import re
        pattern = r"```json_action\s*([\s\S]*?)\s*```"
        matches = re.findall(pattern, reply)

        user_id = state["user_id"]
        for action_str in matches:
            try:
                action_data = json.loads(action_str.strip())
                actions_list = action_data if isinstance(action_data, list) else [action_data]

                for item in actions_list:
                    action_name = item.get("action")
                    data = item.get("data", {})

                    if action_name == "create_goal":
                        res = create_user_goal_in_db(
                            user_id=user_id,
                            goal_name=data.get("goal_name", "New Goal"),
                            target_amount=data.get("target_amount", 0.0),
                            saved_amount=data.get("saved_amount", 0.0),
                            deadline=data.get("deadline"),
                        )
                        if res.get("success"):
                            remember_user_preference(
                                user_id,
                                f"Added financial goal '{data.get('goal_name')}' target ₹{data.get('target_amount')}",
                                "goal",
                            )

                    elif action_name == "create_transaction":
                        cat = str(data.get("category", "General")).strip()
                        merchant = str(data.get("merchant", "Unknown")).strip()
                        
                        # Auto-tag income if merchant or category implies deposit/bonus/income/salary
                        m_lower = merchant.lower()
                        c_lower = cat.lower()
                        if any(kw in m_lower or kw in c_lower for kw in ["bonus", "income", "salary", "deposit", "deposite", "transfer in", "paycheck", "credit"]):
                            cat = "Income"

                        res = create_user_transaction_in_db(
                            user_id=user_id,
                            amount=data.get("amount", 0.0),
                            category=cat,
                            merchant=merchant,
                            date=data.get("date"),
                        )
                        if res.get("success"):
                            remember_user_preference(
                                user_id,
                                f"Added transaction ₹{data.get('amount')} ({cat}/{merchant})",
                                "transaction",
                            )

                    elif action_name == "create_budget":
                        res = create_user_budget_in_db(
                            user_id=user_id,
                            category=data.get("category", "General"),
                            monthly_limit=data.get("monthly_limit", 0.0),
                            month=data.get("month"),
                        )
                        if res.get("success"):
                            remember_user_preference(
                                user_id,
                                f"Set budget ₹{data.get('monthly_limit')} for {data.get('category')}",
                                "budget",
                            )
            except Exception as action_err:
                print(f"[Action Execution Exception]: {action_err}")

        # Strip out all json_action code blocks from the user-facing text
        reply = re.sub(pattern, "", reply).strip()

    return {"messages": [AIMessage(content=reply)]}


def create_financial_agent():
    """Compiles the LangGraph multi-node financial reasoning agent workflow with entry security guardrail."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("security_guardrail", security_guardrail_node)
    workflow.add_node("fetch_db_context", db_context_node)
    workflow.add_node("recall_memories", memory_recall_node)
    workflow.add_node("llm_reasoning", llm_reasoning_node)
    workflow.add_node("save_user_preferences", memory_save_node)

    # Set Graph Edges
    workflow.set_entry_point("security_guardrail")

    # Conditional edge: guardrail check -> END or fetch_db_context
    workflow.add_conditional_edges(
        "security_guardrail",
        route_after_guardrail,
        {
            END: END,
            "fetch_db_context": "fetch_db_context",
        },
    )

    workflow.add_edge("fetch_db_context", "recall_memories")
    workflow.add_edge("recall_memories", "llm_reasoning")
    workflow.add_edge("llm_reasoning", "save_user_preferences")
    workflow.add_edge("save_user_preferences", END)

    return workflow.compile()


financial_agent = create_financial_agent()