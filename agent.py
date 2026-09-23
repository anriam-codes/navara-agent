import json
import time

from openai import OpenAI, RateLimitError

import config
from diagnostics import check_service_status
from retrieve import search

llm = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

SYSTEM = """You are a technical support assistant for Kafka, Docker, PostgreSQL and FastAPI.
Use the tools to find relevant documentation before answering.
- search_docs: general concepts and configuration explanations.
- search_troubleshooting: specific errors, symptoms, and fixes.
- check_service_status: checks if a local service is actually reachable right now.
For connectivity questions ("can't connect", "connection refused", "is X running"),
call check_service_status alongside a troubleshooting search, and combine both in your answer.
Call each tool at most once per distinct topic. If a tool returns no relevant results,
do not repeat it with a reworded query — try the other tool once if it might help, otherwise
tell the user you don't have enough information. Be concise: cause, diagnosis, fix."""

NO_ANSWER = "I couldn't find relevant information in the knowledge base to answer that reliably."

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search conceptual/reference documentation (what things are, how they work, config settings).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tech": {"type": "string", "enum": ["kafka", "docker", "postgresql", "fastapi"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_troubleshooting",
            "description": "Search troubleshooting documentation (errors, symptoms, causes, fixes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tech": {"type": "string", "enum": ["kafka", "docker", "postgresql", "fastapi"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_status",
            "description": "Check whether a local service (kafka, postgresql, fastapi, docker) is currently reachable on its default port.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "enum": ["kafka", "postgresql", "fastapi", "docker"]},
                },
                "required": ["service"],
            },
        },
    },
]


def _search_by_doc_type(query, tech, doc_suffix):
    tech = tech[0] if isinstance(tech, list) else tech  # Gemini sometimes sends tech as a list
    tech = tech.lower() if tech else None
    hits = search(query, config.TOP_K, tech, doc_type=doc_suffix)
    return [h for h in hits if h["score"] >= config.MIN_SCORE]


def search_docs(query, tech=None):
    return _search_by_doc_type(query, tech, "basics.md")


def search_troubleshooting(query, tech=None):
    return _search_by_doc_type(query, tech, "trouble.md")


TOOL_FUNCS = {
    "search_docs": search_docs,
    "search_troubleshooting": search_troubleshooting,
    "check_service_status": check_service_status,
}


def format_sources(sources):
    seen = []
    for s in sources:
        if s not in seen:
            seen.append(s)
    return seen


def _call_llm(messages):
    for attempt in range(3):
        try:
            return llm.chat.completions.create(
                model=config.LLM_MODEL, temperature=0, messages=messages, tools=TOOLS
            )
        except RateLimitError:
            raise  # quota exhaustion won't fix itself in seconds — fail fast
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def ask(question, history=None, max_rounds=4):
    """history: list of prior {"role": ..., "content": ...} turns for follow-up context. Optional."""
    messages = [{"role": "system", "content": SYSTEM}, *(history or []), {"role": "user", "content": question}]
    tools_used, sources, retrieved_anything = [], [], False

    for _ in range(max_rounds):
        response = _call_llm(messages)
        msg = response.choices[0].message

        if not msg.tool_calls:
            answer = msg.content or ""
            if not retrieved_anything:
                # model answered without retrieving anything grounded — don't let it invent facts
                answer = NO_ANSWER
            return {
                "answer": answer,
                "sources": format_sources(sources),
                "tools_used": tools_used,
                "messages": messages + [{"role": "assistant", "content": answer}],
            }

        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = TOOL_FUNCS[call.function.name](**args)
            tools_used.append(call.function.name)
            print(f"  [{call.function.name}] args={args} → "
                  f"{result['status'] if call.function.name == 'check_service_status' else f'{len(result)} hits'}")

            if call.function.name == "check_service_status":
                result_text = f"{result['service']}: {result['status']} — {result['detail']}"
            else:
                if result:
                    retrieved_anything = True
                    sources.extend(f"{h['source']} (score: {h['score']:.2f})" for h in result)
                result_text = "\n\n".join(h["text"] for h in result) or "No relevant results."

            messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text})

    return {
        "answer": "I wasn't able to settle on an answer in time.",
        "sources": format_sources(sources),
        "tools_used": tools_used,
        "messages": messages,
    }

if __name__ == "__main__":
    history = []
    while q := input("Question (empty to quit)> ").strip():
        result = ask(q, history)
        history = result["messages"][1:]  # drop system prompt, keep it for next turn's context

        print("\nAnswer\n──────")
        print(result["answer"])
        print("\nTools used:", result["tools_used"] or "none")
        print("\nSources:")
        for s in result["sources"]:
            print(f"  - {s}")
        if not result["sources"]:
            print("  none")
        print()