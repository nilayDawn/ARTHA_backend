import json
from google import genai
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.tools import fetch_user_financial_context, fetch_relevant_memories,remember_user_preference
from app.core.config import settings


def db_context_node(state: AgentState) -> Dict[str, Any]:
    """Node: Pulls recent transactions, budgets, and goals from Supabase."""
    user_id = state["user_id"]
    context = fetch_user_financial_context(user_id)
    return {"db_context": context}


def memory_recall_node(state: AgentState) -> Dict[str, Any]:
    """Node: Retrieves contextual long-term user memories and user preferences from Qdrant."""
    user_id = state["user_id"]
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    memories = fetch_relevant_memories(user_id, last_user_msg) if last_user_msg else []
    return {"memories": memories}

def memory_save_node(state: AgentState) -> Dict[str, Any]:
    """Node: Saves user preferences and memories to Qdrant."""
    user_id = state['user_id']
    last_user_msg = " "
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break
    user_preferences = remember_user_preference(user_id, last_user_msg, category="preference") if last_user_msg else []
    return {"user_preferences": user_preferences}


def llm_reasoning_node(state: AgentState) -> Dict[str, Any]:
    """Node: Generates standard response using Gemini 2.5 Flash."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    system_prompt = f"""
    You are Finance Manager AI, a knowledgeable, empathetic, and sharp personal AI financial employee.
    
    Current User Context:
    - User ID: {state['user_id']}
    - Financial Data (Transactions, Budgets, Goals): {json.dumps(state.get('db_context', {}))}
    - Long-Term User Memories & Preferences: {json.dumps(state.get('memories', []))}
    
    Guidelines:
    1. Provide precise, actionable financial insights based on the user's data.
    2. If answering about spending or budgets, ground your response using the provided financial context.
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
    """Compiles the LangGraph multi-node financial reasoning agent workflow."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("fetch_db_context", db_context_node)
    workflow.add_node("recall_memories", memory_recall_node)
    workflow.add_node("llm_reasoning", llm_reasoning_node)
    workflow.add_node("save_user_preferences", memory_save_node)

    # Set Graph Edges
    workflow.set_entry_point("fetch_db_context")
    workflow.add_edge("fetch_db_context", "recall_memories")
    workflow.add_edge("recall_memories", "llm_reasoning")
    workflow.add_edge("llm_reasoning", "save_user_preferences")
    workflow.add_edge("save_user_preferences", END)

    return workflow.compile()


financial_agent = create_financial_agent()