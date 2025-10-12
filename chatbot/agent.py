"""
Core Chatbot Agent
------------------
LangChain ReAct agent that intelligently routes insurance-related queries
to specialized tools for:
- Fraud scoring
- Alarm explanations
- Policy guidance (via RAG)
- Claim rejection Q&A

🧠 LLM: OpenAI GPT-3.5-turbo
🧰 Tools: submit_and_score, explain_alarms, retrieve_guidance, qa_handler
📄 Prompts: system_prompt.md, user_examples.md, rejection_prompt.md
📦 Session: Maintains conversation history via utils/session_manager

Usage:
    agent, session = create_agent()
    response = run_agent("Score this claim for fraud.", session_id="1234")
"""

import os
from dotenv import load_dotenv
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import AIMessage, HumanMessage

# Local imports
from .tools import submit_and_score, explain_alarms, retrieve_guidance, qa_handler
from .utils.session_manager import SessionManager
from .utils.formatter import format_chat_response
from .utils.logger import logger
from .config.settings import settings
from .config.constants import MAX_TOKENS

# Load environment variables
load_dotenv()


# =========================================================
# 🧩 Prompt Loaders
# =========================================================
def load_prompt(file_path: str) -> str:
    """Safely load a markdown-based prompt file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {file_path}")
        return ""


SYSTEM_PROMPT = load_prompt("chatbot/prompts/system_prompt.md")
USER_EXAMPLES = load_prompt("chatbot/prompts/user_examples.md")
REJECTION_PROMPT = load_prompt("chatbot/prompts/rejection_prompt.md")


# =========================================================
# ⚙️ Agent Factory
# =========================================================
def create_agent(session_id: str | None = None):
    """
    Create and configure a LangChain ReAct agent.
    Args:
        session_id: Optional. For maintaining conversation history.
    Returns:
        (AgentExecutor, SessionManager)
    """
    # Configure LLM
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0.1,  # Lower = more factual and consistent
        openai_api_key=settings.OPENAI_API_KEY,
        max_tokens=MAX_TOKENS,
    )

    # Register tools
    tools = [
        submit_and_score,
        explain_alarms,
        retrieve_guidance,
        qa_handler,
    ]

    # Construct unified ReAct prompt
    react_prompt = PromptTemplate(
        template=f"""{SYSTEM_PROMPT}

Few-Shot Examples:
{USER_EXAMPLES}

Rejection-Specific (when fraud detected):
{REJECTION_PROMPT}

You are an intelligent insurance assistant that reasons and uses tools.

Question: {{input}}
Thought: {{agent_scratchpad}}""",
        input_variables=["input", "agent_scratchpad"],
    )

    # Create ReAct agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=react_prompt,
    )

    # Wrap with executor for stateful operation
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.DEBUG,
        handle_parsing_errors=True,
        max_iterations=5,
        early_stopping_method="generate",
    )

    # Session state handler
    session = SessionManager(session_id) if session_id else None
    return executor, session


# =========================================================
# 🧠 Run Query Through Agent
# =========================================================
def run_agent(query: str, session_id: str | None = None) -> str:
    """
    Process a user query through the chatbot agent.

    Args:
        query (str): User input text.
        session_id (str, optional): For persistent context.
    Returns:
        str: Model's formatted reply.
    """
    agent, session = create_agent(session_id)

    # Track user message
    if session:
        session.add_message("human", query)

    try:
        # Execute ReAct reasoning cycle
        result = agent.invoke({"input": query})
        output = result.get("output", "Sorry, I couldn’t process that request.")

        # Format final message for frontend
        formatted = format_chat_response(output)

        # Track AI message
        if session:
            session.add_message("ai", formatted)

        return formatted

    except Exception as e:
        logger.error(f"Agent runtime error: {e}")
        return "⚠️ An internal error occurred. Please try again later."


# =========================================================
# 🧩 CLI (for quick testing)
# =========================================================
if __name__ == "__main__":
    print("💬 Chatbot Agent Interactive Console (Ctrl+C to exit)")
    session_id = "local_test_session"

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break

            response = run_agent(user_input, session_id=session_id)
            print(f"\nAssistant: {response}")

        except KeyboardInterrupt:
            print("\n🛑 Exiting.")
            break
