"""LangGraph Shader Agent：使用工具调用实现 GLSL 生成+自检循环。"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _build_agent_node(llm: Any, system_prompt: str):
    """构建 agent 节点：绑定 tools，注入 system prompt。"""

    def _agent(state: AgentState) -> dict:
        messages = state["messages"]
        # 确保 system prompt 在第一条
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        elif isinstance(messages[0], SystemMessage) and messages[0].content != system_prompt:
            messages = [SystemMessage(content=system_prompt)] + list(messages[1:])

        response = llm.invoke(messages)
        return {"messages": [response]}

    return _agent


def _should_continue(state: AgentState) -> str:
    """条件路由：最后一条消息是否包含 tool_calls。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_shader_agent(
    llm: Any,
    tools: list,
    system_prompt: str = "",
    max_iterations: int = 15,
):
    """构建 LangGraph Shader Agent 图。

    Args:
        llm: LLM 实例（ChatOpenAI 或 mock RunnableLambda）。对于 ChatOpenAI，
             可通过 llm.bind_tools(tools) 预先绑定工具。
        tools: @tool 函数列表
        system_prompt: 系统提示词
        max_iterations: 最大 agent-tools 循环次数

    Returns:
        编译后的 LangGraph StateGraph
    """
    # 尝试绑定 tools（ChatOpenAI 支持 bind_tools，mock RunnableLambda 忽略额外参数）
    try:
        llm_with_tools = llm.bind_tools(tools)
    except (AttributeError, TypeError):
        llm_with_tools = llm

    if not system_prompt:
        root = Path(__file__).resolve().parent
        prompt_path = root / "system_prompt.md"
        if prompt_path.exists():
            system_prompt = prompt_path.read_text(encoding="utf-8-sig")

    tool_node = ToolNode(tools)
    agent_node = _build_agent_node(llm_with_tools, system_prompt)

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        _should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()
