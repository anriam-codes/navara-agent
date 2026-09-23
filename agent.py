import json

from openai import OpenAI
from qdrant_client.models import FieldCondition, Filter, MatchText

import config
from retrieve import search

llm = OpenAI(
    base_url=config.LLM_BASE_URL,
    api_key=config.LLM_API_KEY
)

SYSTEM = """You are a technical support assistant for Kafka, Docker, PostgreSQL and FastAPI.

Use the available tools to find relevant documentation before answering.

- search_docs: general concepts and configuration explanations.
- search_troubleshooting: specific errors, symptoms, causes, and fixes.

Rules:
- Call one or both tools when useful.
- Only answer using information supported by the retrieved documentation.
- If the tools return no relevant information, clearly say that the knowledge base
  does not contain enough information.
- Do not invent commands, configuration values, causes, or fixes.
- Be concise: cause, diagnosis, fix.
- When previous conversation context exists, use it to understand follow-up questions.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "Search conceptual/reference documentation such as what things are, "
                "how they work, and configuration settings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tech": {
                        "type": "string",
                        "enum": ["kafka", "docker", "postgresql", "fastapi"]
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_troubleshooting",
            "description": (
                "Search troubleshooting documentation for errors, symptoms, "
                "causes, diagnosis steps, and fixes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tech": {
                        "type": "string",
                        "enum": ["kafka", "docker", "postgresql", "fastapi"]
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def normalize_tech(tech):
    """Gemini may occasionally return ['kafka'] instead of 'kafka'."""
    if isinstance(tech, list):
        return tech[0] if tech else None
    return tech


def _search_by_doc_type(query, tech, doc_suffix):
    """Search Qdrant and keep only the requested document type."""
    tech = normalize_tech(tech)

    hits = search(query, config.TOP_K, tech)

    hits = [
        h for h in hits
        if h["source"].endswith(doc_suffix)
        and h["score"] >= config.MIN_SCORE
    ]

    return hits


def search_docs(query, tech=None):
    return _search_by_doc_type(query, tech, "basics.md")


def search_troubleshooting(query, tech=None):
    return _search_by_doc_type(query, tech, "trouble.md")


TOOL_FUNCS = {
    "search_docs": search_docs,
    "search_troubleshooting": search_troubleshooting,
}


def format_sources(hits):
    """Create clean source information for the final result."""
    return [
        {
            "source": h["source"],
            "score": round(h["score"], 3),
        }
        for h in hits
    ]


def ask(question, history=None, max_rounds=4):
    """
    Ask the agent a question.

    history contains previous messages from the current CLI conversation.
    """
    messages = [
        {"role": "system", "content": SYSTEM}
    ]

    if history:
        messages.extend(history)

    messages.append({
        "role": "user",
        "content": question
    })

    tools_used = []
    sources = []
    retrieved_anything = False

    for _ in range(max_rounds):
        response = llm.chat.completions.create(
            model=config.LLM_MODEL,
            temperature=0,
            messages=messages,
            tools=TOOLS,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            answer = msg.content or ""

            if not retrieved_anything:
                answer = (
                    "I couldn't find relevant information in the knowledge base "
                    "to answer that reliably."
                )

            return {
                "answer": answer,
                "sources": list(dict.fromkeys(
                    (s["source"], s["score"]) for s in sources
                )),
                "tools_used": tools_used,
                "history": messages + [
                    {
                        "role": "assistant",
                        "content": answer
                    }
                ],
            }

        messages.append(msg)

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")

            tool_name = call.function.name
            tool_func = TOOL_FUNCS.get(tool_name)

            if not tool_func:
                result_text = f"Unknown tool: {tool_name}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result_text,
                })
                continue

            hits = tool_func(**args)

            print(
                f"  [{tool_name}] "
                f"args={args} → {len(hits)} hits"
            )

            tools_used.append(tool_name)

            if hits:
                retrieved_anything = True

            sources.extend(format_sources(hits))

            if hits:
                result_text = "\n\n".join(
                    f"Source: {h['source']}\n"
                    f"Relevance: {h['score']:.3f}\n"
                    f"{h['text']}"
                    for h in hits
                )
            else:
                result_text = (
                    "No relevant results were found in the knowledge base."
                )

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result_text,
            })

    return {
        "answer": "I wasn't able to settle on an answer in time.",
        "sources": [],
        "tools_used": tools_used,
        "history": messages,
    }


if __name__ == "__main__":
    history = []

    while q := input("Question (empty to quit)> ").strip():
        result = ask(q, history=history)

        print("\nAnswer")
        print("──────")
        print(result["answer"])

        print("\nTools used:", result["tools_used"] or "none")

        print("\nSources:")
        if result["sources"]:
            for source, score in result["sources"]:
                print(f"  - {source} (score: {score})")
        else:
            print("  none")

        print()

        history = result["history"]