import json
from typing import Any

from google import genai
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agent.guardrail import evaluate_security_guardrail
from app.agent.state import AgentState
from app.agent.tools import (
    fetch_relevant_memories,
    fetch_user_financial_context,
    remember_user_preference,
)
from app.core.config import settings


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


def memory_save_node(state: AgentState) -> dict[str, Any]:
    """Node: Saves user preferences and memories to Qdrant."""
    user_id = state["user_id"]
    last_user_msg = " "
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break
    user_preferences = (
        remember_user_preference(user_id, last_user_msg, category="preference")
        if last_user_msg
        else []
    )
    return {"user_preferences": user_preferences}


def llm_reasoning_node(state: AgentState) -> dict[str, Any]:
    """Node: Generates standard response using Gemini 2.5 Flash."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    system_prompt = f"""
    You are ARTHA AI, a knowledgeable, empathetic, and sharp personal AI financial employee.
    
    Current User Context:
    - User ID: {state['user_id']}
    - Financial Data (Transactions, Budgets, Goals): {json.dumps(state.get('db_context', {}))}
    - Long-Term User Memories & Preferences: {json.dumps(state.get('memories', []))}
    
    Guidelines:
    1. Provide precise, actionable financial insights based on the user's data.
    2. Ground your response strictly using the provided financial context.
    3. Keep answers conversational, helpful, concise, and easy to read using markdown formatting.
    """

    # Prepare message history
    formatted_contents = [{"role": "user", "parts": [{"text": system_prompt}]}]

    for msg in state["messages"]:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        formatted_contents.append({"role": role, "parts": [{"text": msg.content}]})

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=formatted_contents,
    )

    reply = response.text or "I was unable to analyze your financial query at this time."
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