from __future__ import annotations

import random
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/question-bank", tags=["question-bank"])

QUESTIONS = [
    {"id":"de-001","category":"Data Engineering","difficulty":"medium","question":"Explain how you would design a scalable batch ETL pipeline in Azure."},
    {"id":"de-002","category":"Data Engineering","difficulty":"medium","question":"How do you implement incremental loading and handle late-arriving data?"},
    {"id":"de-003","category":"Data Engineering","difficulty":"hard","question":"How would you troubleshoot a production pipeline that suddenly became slow?"},
    {"id":"sql-001","category":"SQL","difficulty":"easy","question":"What is the difference between WHERE and HAVING?"},
    {"id":"sql-002","category":"SQL","difficulty":"medium","question":"How would you find the second-highest salary without using TOP or LIMIT?"},
    {"id":"sql-003","category":"SQL","difficulty":"hard","question":"Explain window functions and give a practical use case."},
    {"id":"spark-001","category":"Spark","difficulty":"medium","question":"What is the difference between repartition and coalesce in Spark?"},
    {"id":"spark-002","category":"Spark","difficulty":"hard","question":"Explain Spark shuffles, data skew, and techniques to mitigate skew."},
    {"id":"azure-001","category":"Azure","difficulty":"medium","question":"Compare Azure Data Factory Integration Runtime types and when you would use them."},
    {"id":"azure-002","category":"Azure","difficulty":"medium","question":"How would you secure data in ADLS Gen2 using RBAC and ACLs?"},
    {"id":"python-001","category":"Python","difficulty":"easy","question":"What are generators in Python and why are they useful for data processing?"},
    {"id":"python-002","category":"Python","difficulty":"medium","question":"How would you process a very large file in Python without loading it fully into memory?"},
    {"id":"behavioral-001","category":"Behavioral","difficulty":"easy","question":"Tell me about a difficult production incident and how you resolved it."},
    {"id":"behavioral-002","category":"Behavioral","difficulty":"medium","question":"Describe a time you disagreed with a technical decision and what you did."},
    {"id":"project-001","category":"Project","difficulty":"medium","question":"Walk me through one of your data engineering projects from source to consumption."},
]

@router.get("")
async def list_questions(category: str | None = Query(default=None), difficulty: str | None = Query(default=None), search: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=100)) -> dict:
    items = QUESTIONS
    if category:
        items = [q for q in items if q["category"].lower() == category.lower()]
    if difficulty:
        items = [q for q in items if q["difficulty"].lower() == difficulty.lower()]
    if search:
        needle = search.lower()
        items = [q for q in items if needle in q["question"].lower() or needle in q["category"].lower()]
    return {"total": len(items), "questions": items[:limit]}

@router.get("/random")
async def random_question(category: str | None = None) -> dict:
    pool = [q for q in QUESTIONS if not category or q["category"].lower() == category.lower()]
    return random.choice(pool) if pool else {"detail": "No questions found"}

@router.get("/categories")
async def categories() -> list[str]:
    return sorted({q["category"] for q in QUESTIONS})
