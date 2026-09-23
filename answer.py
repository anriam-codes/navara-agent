import re

from openai import OpenAI

import config
from retrieve import search

llm = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

SYSTEM = """You are a technical support assistant for Kafka, Docker, PostgreSQL and FastAPI.
Answer using ONLY the documentation excerpts provided inside <context>.
If the excerpts do not contain enough information to answer the question, say so clearly instead of guessing.
Be concise: likely cause first, then diagnostic steps, then the fix.
Do not mention "the context" or "the excerpts"; just answer."""

NO_ANSWER = "I don't have enough information in my knowledge base to answer that reliably."


def ask(question):
    hits = [h for h in search(question, config.TOP_K) if h["score"] >= config.MIN_SCORE]
    if not hits:
        return {"answer": NO_ANSWER, "sources": []}

    context = "\n\n".join(
        f'<doc source="{h["source"]}" section="{h["section"]}">\n{h["text"]}\n</doc>'
        for h in hits
    )
    response = llm.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}"},
        ],
    )
    text = response.choices[0].message.content or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # harmless no-op on Gemini

    sources = list(dict.fromkeys(h["source"] for h in hits))  # unique, in score order
    return {"answer": text, "sources": sources}


if __name__ == "__main__":
    while q := input("Question (empty to quit)> ").strip():
        result = ask(q)
        print("\nAnswer\n──────")
        print(result["answer"])
        print("\nSources\n───────")
        print("\n".join(result["sources"]) or "none")
        print()