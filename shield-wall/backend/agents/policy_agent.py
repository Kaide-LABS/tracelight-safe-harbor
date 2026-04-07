import asyncio
from backend.models.schemas import SecurityQuestion, PolicyCitation
from backend.policy_store.retriever import retrieve_policy_citations
from backend.config import ShieldWallSettings

async def gather_policy_citations(questions: list[SecurityQuestion], collection, settings: ShieldWallSettings) -> dict[int, list[PolicyCitation]]:
    results = {}
    tasks = []
    
    async def _fetch(q):
        if q.requires_policy:
            citations = await retrieve_policy_citations(q.normalized_query, collection, settings)
            for c in citations:
                c.question_id = q.id
            return q.id, citations
        return q.id, []

    for q in questions:
        tasks.append(_fetch(q))
        
    fetched = await asyncio.gather(*tasks)
    
    for qid, citations in fetched:
        if citations:
            results[qid] = citations
            
    return results
