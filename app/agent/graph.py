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

    is_blocked, refusal_message = evaluate_security_guardrail(last_user_msg)

    if is_blocked:
        return {
            "is_blocked": True,
            "messages": [AIMessage(content=refusal_message)],
        }

    return {"is_blocked": False}


def route_after_guardrail(state: AgentState) -> str:
    """
    Conditional Edge Router:
    If blocked by security guardrail, immediately terminate graph execution.
    Otherwise, proceed to database context retrieval.
    """
    if state.get("is_blocked"):
        return END
    return "fetch_db_context"


def db_context_node(state: AgentState) -> dict[str, Any]:
    """Node: Pulls recent transactions, budgets, and goals from Supabase."""
    user_id = state["user_id"]
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

    memories = fetch_relevant_memories(user_id, last_user_msg) if last_user_msg else []
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
        return {"user_preferences": []}

    # Only save if message expresses a long-term preference/habit
    lower_msg = last_user_msg.lower()
    is_important = any(kw in lower_msg for kw in PREFERENCE_KEYWORDS)

    if is_important:
        remember_user_preference(user_id, last_user_msg.strip(), category="preference")
        return {"user_preferences": [last_user_msg]}

    return {"user_preferences": []}


def llm_reasoning_node(state: AgentState) -> dict[str, Any]:
    """Node: Generates response using Gemini Flash and executes database mutation actions."""
    from app.agent.tools import format_compact_financial_context

    compact_db_summary = format_compact_financial_context(state.get("db_context", {}))
    
    system_prompt = f"""
    You are ARTHA AI, a dedicated, knowledgeable, and sharp personal AI financial employee.
    
    Current User Context:
    - User ID: {state['user_id']}
    - Financial Data Summary: {compact_db_summary}
    - Long-Term Memories: {json.dumps(state.get('memories', []))}
    
    Guidelines:
    1. Provide precise, actionable financial insights based on the user's data.
    2. Ground your response strictly using the provided financial context.
    3. Keep answers conversational, helpful, concise, and easy to read using markdown formatting.
    4. ACTION EXECUTION:
       If the user asks you to ADD, CREATE, SET, or LOG a new financial goal, transaction, or budget:
       You MUST append a JSON action block at the VERY END of your text inside triple backticks tagged ```json_action ... ```.

       - Goal Creation Format:
       ```json_action
       {{"action": "create_goal", "data": {{"goal_name": "Laptop", "target_amount": 82000.0, "saved_amount": 0.0}}}}
       ```

       - Transaction Creation Format:
       ```json_action
       {{"action": "create_transaction", "data": {{"amount": 500.0, "category": "Groceries", "merchant": "Supermarket"}}}}
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

    # Parse and execute structured action blocks (e.g. create_goal, create_transaction, create_budget)
    if "```json_action" in reply:
        try:
            parts = reply.split("```json_action")
            action_block = parts[1].split("```")[0].strip()
            action_data = json.loads(action_block)
            action_name = action_data.get("action")
            data = action_data.get("data", {})
            user_id = state["user_id"]

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
                        f"Added new financial goal '{data.get('goal_name')}' with target amount ₹{data.get('target_amount')}",
                        "goal",
                    )

            elif action_name == "create_transaction":
                res = create_user_transaction_in_db(
                    user_id=user_id,
                    amount=data.get("amount", 0.0),
                    category=data.get("category", "General"),
                    merchant=data.get("merchant", "Unknown"),
                    date=data.get("date"),
                )
                if res.get("success"):
                    remember_user_preference(
                        user_id,
                        f"Added transaction of ₹{data.get('amount')} for {data.get('category')} ({data.get('merchant')})",
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
                        f"Set monthly budget of ₹{data.get('monthly_limit')} for {data.get('category')}",
                        "budget",
                    )

            # Strip the json_action code block from final user text
            clean_text = parts[0].strip()
            remaining = parts[1].split("```", 1)
            if len(remaining) > 1 and remaining[1].strip():
                clean_text += "\n\n" + remaining[1].strip()
            reply = clean_text
        except Exception as err:
            print(f"[Action Execution Error]: {err}")

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