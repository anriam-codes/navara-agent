from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import ask

app = FastAPI(title="Navara", description="Agentic RAG for Kafka/Docker/PostgreSQL/FastAPI troubleshooting")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    tools_used: list[str]


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest):
    try:
        result = ask(req.question)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM/retrieval error: {e}")
    return AskResponse(answer=result["answer"], sources=result["sources"], tools_used=result["tools_used"])


@app.get("/health")
def health():
    return {"status": "ok"}