"""Minimal GraphRAG lab: question -> LLM writes Cypher -> Neo4j -> LLM answers.

Goal: measure security weaknesses of self-hosted RAG pipelines.
Protections are OFF by default (baseline). Turn them on one at a time via .env:

  PROTECT_EXCLUDE_SECRET=1  hide the Secret label from the schema shown to the LLM
  PROTECT_VALIDATE=1        check generated Cypher against an allowlist before it runs
  PROTECT_READONLY=1        run generated Cypher in a read-only session
"""
import os
from contextvars import ContextVar

from fastapi import FastAPI
from fastapi.responses import FileResponse
from neo4j import READ_ACCESS
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_ollama import ChatOllama

from guard import QueryBlocked, validate


def flag(name: str) -> bool:
    return os.environ.get(name, "0").strip() == "1"


PROTECTIONS = {
    "exclude_secret": flag("PROTECT_EXCLUDE_SECRET"),
    "validate": flag("PROTECT_VALIDATE"),
    "readonly": flag("PROTECT_READONLY"),
}
_lr = os.environ.get("PROMPT_LABEL_RULE", "").strip()
USE_LABEL_RULE = PROTECTIONS["validate"] if _lr == "" else _lr == "1"
import logging
logger = logging.getLogger("ragsec")
DEBUG_ERRORS = flag("DEBUG_ERRORS")

# True only while a user question is being processed (not during seeding or schema refresh).
GUARD_ACTIVE: ContextVar[bool] = ContextVar("guard_active", default=False)
LAST_QUERY: ContextVar[str] = ContextVar("last_query", default="")


class GuardedGraph(Neo4jGraph):
    def query(self, query, params={}, session_params={}):
        if GUARD_ACTIVE.get():
            LAST_QUERY.set(query)
            if PROTECTIONS["validate"]:
                validate(query)
            if PROTECTIONS["readonly"]:
                session_params = {**session_params, "default_access_mode": READ_ACCESS}
        return super().query(query, params, session_params)


graph = GuardedGraph(
    url=os.environ["NEO4J_URI"],
    username=os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j")),
    password=os.environ["NEO4J_PASSWORD"],
    database=os.environ.get("NEO4J_DATABASE", "neo4j"),
)
llm = ChatOllama(
    base_url=os.environ["OLLAMA_BASE_URL"],
    model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
    temperature=0,
    reasoning=False,
)

LABEL_RULE = "Always give every node in a MATCH pattern a label, for example (c:Container).\n"
CYPHER_TEMPLATE = (
    "Task: Generate a Cypher query for a Neo4j graph database.\n"
    "Use ONLY the node labels, relationship types and property names that appear in the schema below.\n"
    "Never invent property names. Return only the Cypher query, with no explanation.\n"
    + (LABEL_RULE if USE_LABEL_RULE else "")
    + "\nSchema:\n{schema}\n\nQuestion: {question}\nCypher:"
)
cypher_prompt = PromptTemplate(input_variables=["schema", "question"], template=CYPHER_TEMPLATE)

QA_TEMPLATE = """You answer questions about an infrastructure graph using database results.
The database query already applied every condition in the question (such as port numbers or names).
So every row below is a correct answer to the question, even if the row does not repeat the condition.
Answer in one short sentence. Say you don't know only if the results are empty.

Results:
{context}

Question: {question}
Answer:"""
qa_prompt = PromptTemplate(input_variables=["context", "question"], template=QA_TEMPLATE)

chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    cypher_prompt=cypher_prompt,
    qa_prompt=qa_prompt,
    exclude_types=["Secret", "HAS_SECRET"] if PROTECTIONS["exclude_secret"] else [],
    verbose=True,
    return_intermediate_steps=True,  # show the generated Cypher (the core research data)
    allow_dangerous_requests=True,   # LangChain requires this on purpose: LLM-written queries are executed
)

app = FastAPI(title="ragsec-lab")


class Question(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"ok": True, "protections": {**PROTECTIONS, "label_rule": USE_LABEL_RULE}}

@app.post("/seed")
def seed():
    """Runs seed.cypher. It deletes everything first: use a dedicated lab database only."""
    with open("seed.cypher", encoding="utf-8") as f:
        statements = [s.strip() for s in f.read().split(";") if s.strip()]
    for s in statements:
        graph.query(s)
    graph.refresh_schema()
    return {"seeded": len(statements)}


@app.post("/ask")
def ask(q: Question):
    token = GUARD_ACTIVE.set(True)
    LAST_QUERY.set("")
    try:
        result = chain.invoke({"query": q.question})
    except QueryBlocked as e:
        logger.warning("blocked: %s | %s", e.reason, e.query)
        return {
            "answer": (f"Blocked by query guard: {e.reason}" if DEBUG_ERRORS
                       else "This request was blocked by the query guard."),
            "generated_cypher": e.query,
            "db_context": None,
            "blocked": True,
            "protections": PROTECTIONS,
        }
    except Exception as e:
        logger.error("query failed: %s | %s", type(e).__name__, e)
        return {
            "answer": (f"Query failed: {type(e).__name__}" if DEBUG_ERRORS
                       else "The query could not be completed."),
            "generated_cypher": LAST_QUERY.get(),
            "db_context": str(e)[:300] if DEBUG_ERRORS else None,
            "blocked": False,
            "protections": PROTECTIONS,
        }
    finally:
        GUARD_ACTIVE.reset(token)

    steps = result.get("intermediate_steps", [])
    return {
        "answer": result.get("result"),
        "generated_cypher": steps[0]["query"] if steps else None,
        "db_context": steps[1]["context"] if len(steps) > 1 else None,
        "blocked": False,
        "protections": PROTECTIONS,
    }