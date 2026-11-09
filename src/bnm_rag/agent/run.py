"""Build the agent and answer a question: LangChain 1.x `create_agent` with the four tools, a
structured `Reply`, and the OpenRouter model chain from OPENROUTER_MODELS (first model, then
fallbacks in order). A reply whose citations fail `reply.problems` is sent back to the model
with the reasons, up to MAX_FIXES times.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from bnm_rag.agent.prompt import system_prompt
from bnm_rag.agent.reply import Reply, citation, cited_ids, problems
from bnm_rag.agent.tools import Backend, make_tools, render
from bnm_rag.index.azure import env

MAX_FIXES = 2
RECURSION_LIMIT = 40  # graph steps per attempt; a tool round trip is two
REQUEST_TIMEOUT_MS = 120_000  # per model call; then the retry, then the fallback model


@dataclass
class Answer:
    question: str
    answer: str
    coverage: str
    pointer: str | None
    citations: list[dict]
    sources: dict[str, str]  # chunk_id → the cited paragraph exactly as the model saw it
    model: str | None
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)
    fixes: int = 0
    fixed: list[str] = field(default_factory=list)  # problems the model was sent back to fix
    unresolved: list[str] = field(default_factory=list)  # problems left after MAX_FIXES


def models():
    from langchain_openrouter import ChatOpenRouter

    names = [m.strip() for m in env("OPENROUTER_MODELS").split(",") if m.strip()]
    key = env("OPENROUTER_API_KEY")
    # No timeout by default: one stalled request held an eval question for 20+ minutes.
    return [ChatOpenRouter(model=n, openrouter_api_key=key, temperature=0, max_retries=2,
                           request_timeout=REQUEST_TIMEOUT_MS, app_title="bnm-rag")
            for n in names]


def build_agent(today: dt.date, backend: Backend | None = None, chat_models=None):
    primary, *fallbacks = chat_models or models()
    return create_agent(
        primary,
        tools=make_tools(today, backend),
        system_prompt=system_prompt(today),
        response_format=ToolStrategy(Reply),
        middleware=[ModelFallbackMiddleware(*fallbacks)] if fallbacks else [],
    )


def retrieved_chunks(messages) -> dict[str, dict]:
    """chunk_id → chunk for everything the tools showed the model in this conversation."""
    out = {}
    for m in messages:
        if isinstance(m, ToolMessage) and isinstance(m.artifact, list):
            for c in m.artifact:
                out[c["chunk_id"]] = c
    return out


def _tool_calls(messages) -> list[tuple[str, dict]]:
    return [(tc["name"], tc["args"]) for m in messages if isinstance(m, AIMessage)
            for tc in m.tool_calls if tc["name"] != Reply.__name__]


NO_REPLY = (f"You ended without a final reply. Give your final answer by calling the "
            f"{Reply.__name__} tool (answer, citations, coverage, not_covered_pointer).")


def _last_text(messages) -> str:
    return next((m.text for m in reversed(messages)
                 if isinstance(m, AIMessage) and m.text.strip()), "")


def ask(question: str, today: dt.date | None = None, agent=None) -> Answer:
    today = today or dt.date.today()
    agent = agent or build_agent(today)
    config = {"recursion_limit": RECURSION_LIMIT}
    messages: list = [HumanMessage(question)]
    fixes, fixed = 0, []
    while True:
        state = agent.invoke({"messages": messages}, config=config)
        messages = state["messages"]
        retrieved = retrieved_chunks(messages)
        reply: Reply | None = state.get("structured_response")
        if reply is None:
            # The model ended its turn in plain text instead of calling the Reply tool.
            issues = [NO_REPLY]
            reply = Reply(answer=_last_text(messages) or "No answer.", citations=[],
                          coverage="partial")
        else:
            issues = problems(reply, retrieved)
        if not issues or fixes == MAX_FIXES:
            break
        fixes += 1
        fixed += issues
        messages = [*messages, HumanMessage(
            "Your reply can't be shown yet:\n- " + "\n- ".join(issues)
            + "\nFix this and reply again.")]
    ids = [c for c in cited_ids(reply, retrieved) if c in retrieved]
    model = next((m.response_metadata.get("model_name") for m in reversed(messages)
                  if isinstance(m, AIMessage) and m.response_metadata), None)
    return Answer(
        question=question, answer=reply.answer, coverage=reply.coverage,
        pointer=reply.not_covered_pointer,
        citations=[citation(retrieved[c], today) for c in ids],
        sources={c: render(retrieved[c], today, full=True) for c in ids},
        model=model, tool_calls=_tool_calls(messages), fixes=fixes, fixed=fixed,
        unresolved=issues,
    )
