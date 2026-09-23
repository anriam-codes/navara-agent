import json

from openai import OpenAI
from qdrant_client.models import FieldCondition, Filter, MatchText

import config
from retrieve import search

llm = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

SYSTEM = """You are a technical support assistant for Kafka, Docker, PostgreSQL and FastAPI.
Use the tools to find relevant documentation before answering.
- search_docs: general concepts and configuration explanations.
- search_troubleshooting: specific errors, symptoms, and fixes.
Call one or both if useful. If nothing relevant comes back, say you don't have
enough information instead of guessing. Be concise: cause, diagnosis, fix."""

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
]


def _search_by_doc_type(query, tech, doc_suffix):
    """Same search() as Phase 3/4, plus a filter on which file the chunk came from."""
    extra = Filter(must=[FieldCondition(key="source", match=MatchText(text=doc_suffix))])
    hits = search(query, config.TOP_K, tech)  # tech filter reuses retrieve.py's existing param
    hits = [h for h in hits if h["source"].endswith(doc_suffix) and h["score"] >= config.MIN_SCORE]
    return hits


def search_docs(query, tech=None):
    return _search_by_doc_type(query, tech[0] if isinstance(tech, list) else tech, "basics.md")

def search_troubleshooting(query, tech=None):
    return _search_by_doc_type(query, tech[0] if isinstance(tech, list) else tech, "trouble.md")

TOOL_FUNCS = {"search_docs": search_docs, "search_troubleshooting": search_troubleshooting}


def ask(question, max_rounds=4):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    tools_used, sources = [], []

    for _ in range(max_rounds):
        response = llm.chat.completions.create(
            model=config.LLM_MODEL, temperature=0, messages=messages, tools=TOOLS
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return {"answer": msg.content or "", "sources": list(dict.fromkeys(sources)), "tools_used": tools_used}

        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            hits = TOOL_FUNCS[call.function.name](**args)
            print(f"  [{call.function.name}] args={args} → {len(hits)} hits")
            tools_used.append(call.function.name)
            sources.extend(h["source"] for h in hits)
            result_text = "\n\n".join(h["text"] for h in hits) or "No relevant results."
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text})

    return {"answer": "I wasn't able to settle on an answer in time.", "sources": [], "tools_used": tools_used}


if __name__ == "__main__":
    while q := input("Question (empty to quit)> ").strip():
        result = ask(q)
        print("\nAnswer\n──────")
        print(result["answer"])
        print("\nTools used:", result["tools_used"] or "none")
        print("Sources:", list(dict.fromkeys(result["sources"])) or "none")
        print()