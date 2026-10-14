from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.agent.prompt import LIBRARY_ASSISTANT_PROMPT
from library_management_system.agent.tools import create_library_tools
from library_management_system.config import get_settings

LibraryTool = BaseTool | Callable[..., Any] | dict[str, Any]


def create_library_agent(
    tools: Sequence[LibraryTool] | None = None,
    *,
    sessions: sessionmaker[Session] | None = None,
    borrower_id: str | None = None,
):
    """Create the library assistant with catalog tools unless custom tools are given."""
    configured_tools = (
        create_library_tools(sessions, borrower_id=borrower_id)
        if tools is None
        else list(tools)
    )
    return create_agent(
        model=get_settings().agent_model,
        tools=configured_tools,
        system_prompt=LIBRARY_ASSISTANT_PROMPT,
        name="library_assistant",
    )


def run_agent(
    user_input: str,
    tools: Sequence[LibraryTool] | None = None,
    *,
    sessions: sessionmaker[Session] | None = None,
    borrower_id: str | None = None,
    history: Sequence[BaseMessage] = (),
) -> str:
    """Run one patron request, optionally continuing a conversation."""
    if not user_input.strip():
        raise ValueError("user_input must not be empty")

    result = create_library_agent(
        tools,
        sessions=sessions,
        borrower_id=borrower_id,
    ).invoke({"messages": [*history, HumanMessage(content=user_input)]})
    response = result["messages"][-1].content
    if not isinstance(response, str):
        raise TypeError("The library assistant returned a non-text response.")
    return response
