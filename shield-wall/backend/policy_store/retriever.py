from openai import AsyncOpenAI
from backend.models.schemas import PolicyCitation

async def retrieve_policy_citations(query: str, collection, settings) -> list[PolicyCitation]:
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await openai_client.embeddings.create(model="text-embedding-3-small", input=query)
        query_embedding = resp.data[0].embedding
        
        results = collection.query(query_embeddings=[query_embedding], n_results=settings.policy_top_k)
        
        citations = []
        if results and results["documents"] and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            ids = results["ids"][0]
            
            for i in range(len(docs)):
                # Convert distance to a pseudo-similarity score (cosine distance)
                relevance = max(0.0, 1.0 - distances[i])
                if relevance > 0.3: # Minimum threshold
                    citations.append(PolicyCitation(
                        question_id=0, # set by caller
                        policy_document=metadatas[i].get("source", "Unknown"),
                        section=metadatas[i].get("section", "General"),
                        excerpt=docs[i],
                        relevance_score=relevance,
                        chunk_id=ids[i]
                    ))
        return citations
    except Exception as e:
        print(f"Retrieval error: {e}")
        return []
