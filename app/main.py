"""Minimal GraphRAG Lab: question -> LLM generates Cypher query -> Neo4j -> LLM responds.

Objective: assess security vulnerabilities in a self-hosted RAG pipeline.
This implementation has intentionally been kept minimal; security measures will be tested by
adding or removing them one by one in Weeks 3-4.
"""

import os
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_ollama import ChatOllama
from fastapi.responses import FileResponse

graph = Neo4jGraph(
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

CYPHER_TEMPLATE = """Task: Generate a Cypher query for a Neo4j graph database.
Use ONLY the node labels, relationship types and property names that appear in the schema below.
Never invent property names. Return only the Cypher query, with no explanation.

Schema:
{schema}

Question: {question}
Cypher:"""
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
    verbose=True,
    return_intermediate_steps=True,  # üretilen Cypher'ı görmek için (araştırmanın kalbi)
    allow_dangerous_requests=True,   # LangChain bunu bilerek zorunlu kılıyor: LLM üretimi sorgu çalıştırıyor
)

app = FastAPI(title="ragsec-lab")

@app.get("/")
def index():
    return FileResponse("static/index.html")

class Question(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/seed")
def seed():
    """seed.cypher dosyasını çalıştırır (sadece laboratuvar)."""
    with open("seed.cypher", encoding="utf-8") as f:
        statements = [s.strip() for s in f.read().split(";") if s.strip()]
    for s in statements:
        graph.query(s)
    graph.refresh_schema()
    return {"seeded": len(statements)}


@app.post("/ask")
def ask(q: Question):
    result = chain.invoke({"query": q.question})
    steps = result.get("intermediate_steps", [])
    return {
        "answer": result.get("result"),
        "generated_cypher": steps[0]["query"] if steps else None,
        "db_context": steps[1]["context"] if len(steps) > 1 else None,
    }