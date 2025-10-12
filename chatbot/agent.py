"""
Chatbot Agent
-------------
Creates and runs the LangChain-powered insurance fraud detection agent.

Core responsibilities:
- Initialize LLM (OpenAI)
- Load prompt & tools
- Maintain conversation session (optional)
- Safely invoke reasoning flow with error handling

Usage:
    from chatbot.agent import run_agent
    print(run_agent("Score $5000 accident claim"))
"""

from typing import Optional, Tuple
import os
import traceback

from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI

from chatbot.tools import (
    submit_and_score,
    explain_alarms,
    retrieve_guidance,
    qa_handler,
)
from chatbot.utils.session_manager import SessionManager
from chatbot.utils.formatter import format_chat_response
from chatbot.utils.logger import logger, log_tool_call
from chatbot.config.settings import settings


# =========================================================
# 📘 Prompt Loader
# =========================================================
def load_prompt(file_path: str = "chatbot/prompts/system_prompt.md") -> str:
    """
    Load the system prompt from a Markdown file.

    Args:
        file_path (str): Path to the system prompt file.

    Returns:
        str: Prompt content for the LLM system role.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


# =========================================================
# 🧠 Agent Creation
# =========================================================
def create_agent(session_id: Optional[str] = None) -> Tuple[object, Optional[SessionManager]]:
    """
    Create and initialize the chatbot agent.

    Args:
        session_id (str, optional): Unique chat session ID.

    Returns:
        Tuple[AgentExecutor, Optional[SessionManager]]
    """
    try:
        # Initialize LLM
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY,
            max_tokens=settings.MAX_TOKENS,
        )

        # Load tools
        tools = [
            submit_and_score,
            explain_alarms,
            retrieve_guidance,
            qa_handler,
        ]

        # Initialize session
        session = SessionManager(session_id) if session_id else None

        # Load system prompt
        system_prompt = load_prompt()

        # Create agent with reasoning + tool use
        agent_executor = initialize_agent(
            tools=tools,
            llm=llm,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=settings.DEBUG,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_message": system_prompt
            },
        )

        logger.info(f"✅ Agent initialized (Session: {session_id or 'None'})")
        return agent_executor, session

    except Exception as e:
        logger.error(f"❌ Agent creation failed: {e}")
        raise


# =========================================================
# 🚀 Run Agent
# =========================================================
def run_agent(query: str, session_id: Optional[str] = None) -> str:
    """
    Execute the chatbot agent for a given user query.

    Args:
        query (str): User input or claim description.
        session_id (str, optional): Chat session ID for context persistence.

    Returns:
        str: The chatbot's formatted response.
    """
    try:
        # Initialize
        agent_executor, session = create_agent(session_id)

        if session:
            session.add_message("human", query)

        # Run reasoning + tool invocation
        raw_result = agent_executor.invoke({"input": query})
        response = raw_result.get("output") if isinstance(raw_result, dict) else str(raw_result)

        # Format
        formatted_response = format_chat_response(response)

        if session:
            session.add_message("ai", formatted_response)

        logger.info(f"🧠 Agent response generated for session={session_id}: {formatted_response[:100]}...")
        return formatted_response

    except Exception as e:
        error_message = f"⚠️ An error occurred while processing your request: {str(e)}"
        logger.error(f"Agent error: {e}\n{traceback.format_exc()}")
        return error_message


# =========================================================
# 🧪 Local REPL (for manual testing)
# =========================================================
if __name__ == "__main__":
    print("🧠 Fraud Detection Chatbot — Interactive Mode")
    print("Type 'exit' to quit.\n")

    session_id = "local_session"
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break
        response = run_agent(user_input, session_id)
        print(f"FraudBot: {response}\n")
