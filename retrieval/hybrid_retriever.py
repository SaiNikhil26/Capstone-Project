import os
import sys
import pickle

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    EMBEDDING_MODEL,
    QDRANT_PATH,
    CHILDREN_COLLECTION,
    PARENTS_COLLECTION,
    BM25_INDEX_PATH,
    TOP_K,
    FINAL_TOP_K,
    SEMANTIC_WEIGHT,
    KEYWORD_WEIGHT
)
from logger import get_logger

log = get_logger("hybrid_retriever")


# ─────────────────────────────────────────
# 1. Build Qdrant metadata filter
# ─────────────────────────────────────────

def build_qdrant_filter(filters: dict):
    """
    Converts plain dict into Qdrant Filter object.

    Supported keys:
        difficulty   : str   — e.g. "Beginner"
        min_rating   : float — e.g. 4.5
        organization : str   — e.g. "DeepLearning.AI"
        course_type  : str   — e.g. "Course"
    """
    conditions = []

    if filters.get("difficulty"):
        conditions.append(
            FieldCondition(
                key="difficulty",
                match=MatchValue(value=filters["difficulty"])
            )
        )
        log.debug(f"Filter — difficulty: {filters['difficulty']}")

    if filters.get("min_rating"):
        conditions.append(
            FieldCondition(
                key="rating",
                range=Range(gte=float(filters["min_rating"]))
            )
        )
        log.debug(f"Filter — min_rating: {filters['min_rating']}")

    if filters.get("organization"):
        conditions.append(
            FieldCondition(
                key="organization",
                match=MatchValue(value=filters["organization"])
            )
        )
        log.debug(f"Filter — organization: {filters['organization']}")

    if filters.get("course_type"):
        conditions.append(
            FieldCondition(
                key="course_type",
                match=MatchValue(value=filters["course_type"])
            )
        )
        log.debug(f"Filter — course_type: {filters['course_type']}")

    if not conditions:
        return None

    return Filter(must=conditions)


# ─────────────────────────────────────────
# 2. Semantic search via Qdrant
# ─────────────────────────────────────────

def semantic_search(
    query: str,
    embeddings: OpenAIEmbeddings,
    filters: dict = None
) -> list[Document]:
    """
    Embeds query and searches Qdrant children collection
    for semantically similar child chunks.
    """
    log.debug(f"Semantic search | query: '{query}'")

    client = QdrantClient(path=QDRANT_PATH)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=CHILDREN_COLLECTION,
        embedding=embeddings
    )

    qdrant_filter = build_qdrant_filter(filters) if filters else None

    results = vector_store.similarity_search(
        query=query,
        k=TOP_K,
        filter=qdrant_filter
    )
    log.debug(f"Semantic search returned {results} chunks before closing client")

    client.close()
    log.debug(f"Semantic search returned {len(results)} chunks")
    return results


# ─────────────────────────────────────────
# 3. Keyword search via BM25
# ─────────────────────────────────────────

def keyword_search(query: str) -> list[Document]:
    """
    Searches pre-built BM25 index over keyword-optimized docs.
    """
    log.debug(f"Keyword search | query: '{query}'")

    if not os.path.exists(BM25_INDEX_PATH):
        log.error(f"BM25 index not found at: {BM25_INDEX_PATH}")
        raise FileNotFoundError(
            f"BM25 index not found. "
            f"Run ingestion first: python -m ingestion.ingest"
        )

    with open(BM25_INDEX_PATH, "rb") as f:
        bm25_retriever = pickle.load(f)

    bm25_retriever.k = TOP_K
    results = bm25_retriever.invoke(query)

    log.debug(f"Keyword search returned {results} chunks")
    return results


# ─────────────────────────────────────────
# 4. Manual RRF fusion
# ─────────────────────────────────────────

def reciprocal_rank_fusion(
    semantic_docs: list[Document],
    keyword_docs:  list[Document],
    k: int = 60
) -> list[Document]:
    """
    Merges two ranked lists using Reciprocal Rank Fusion (RRF).

    RRF formula:
        score = 1 / (k + rank)   for each list
        final  = sum of scores across both lists

    Higher combined score = better match in both semantic + keyword.
    k=60 is the standard constant that dampens very high ranks.
    """
    log.debug("Running RRF fusion")

    rrf_scores = {}  # parent_id → combined RRF score
    doc_map    = {}  # parent_id → Document (for dedup)

    # Score from semantic results
    for rank, doc in enumerate(semantic_docs):
        pid = doc.metadata.get("parent_id") or doc.metadata.get("course_id")
        if not pid:
            continue
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
        if pid not in doc_map:
            doc_map[pid] = doc

    # Score from keyword results
    for rank, doc in enumerate(keyword_docs):
        pid = doc.metadata.get("parent_id") or doc.metadata.get("course_id")
        if not pid:
            continue
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
        if pid not in doc_map:
            doc_map[pid] = doc

    # Sort by combined RRF score descending
    ranked_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    fused = [doc_map[pid] for pid in ranked_ids if pid in doc_map]

    log.debug(
        f"RRF fusion complete | "
        f"semantic: {len(semantic_docs)} | "
        f"keyword: {len(keyword_docs)} | "
        f"fused: {len(fused)}"
    )
    return fused


# ─────────────────────────────────────────
# 5. Small-to-Big: fetch parent docs
# ─────────────────────────────────────────

def fetch_parent_docs(
    fused_docs: list[Document],
    filters: dict = None
) -> list[dict]:
    """
    Small-to-Big retrieval with post-fetch filter enforcement.
    """
    log.debug(f"Fetching parent docs for {len(fused_docs)} fused hits")

    # Collect unique parent_ids preserving rank order
    seen       = set()
    parent_ids = []
    for doc in fused_docs:
        pid = doc.metadata.get("parent_id") or doc.metadata.get("course_id")
        if pid and pid not in seen:
            seen.add(pid)
            parent_ids.append(pid)

    log.debug(f"Unique parent_ids from fused docs: {parent_ids}")

    if not parent_ids:
        log.warning("No parent_ids found in fused docs")
        return []

    # Fetch all parents — filter in Python
    client = QdrantClient(path=QDRANT_PATH)
    all_results, _ = client.scroll(
        collection_name=PARENTS_COLLECTION,
        limit=500,
        with_payload=True,
        with_vectors=False
    )
    client.close()

    # Build lookup map
    payload_map = {
        point.payload.get("course_id"): point.payload
        for point in all_results
    }

    # Fetch in rank order + enforce filters
    ordered = []
    for pid in parent_ids:
        if pid not in payload_map:
            continue

        payload = payload_map[pid]

        # Enforce difficulty filter
        if filters and filters.get("difficulty"):
            if payload.get("difficulty") != filters["difficulty"]:
                log.debug(f"Skipping {pid} — difficulty mismatch: {payload.get('difficulty')}")
                continue

        # Enforce min_rating filter
        if filters and filters.get("min_rating"):
            if float(payload.get("rating", 0)) < float(filters["min_rating"]):
                log.debug(f"Skipping {pid} — rating too low: {payload.get('rating')}")
                continue

        # Enforce organization filter
        if filters and filters.get("organization"):
            if payload.get("organization") != filters["organization"]:
                log.debug(f"Skipping {pid} — org mismatch: {payload.get('organization')}")
                continue

        # Enforce course_type filter
        if filters and filters.get("course_type"):
            if payload.get("course_type") != filters["course_type"]:
                log.debug(f"Skipping {pid} — type mismatch: {payload.get('course_type')}")
                continue

        ordered.append(payload)

        if len(ordered) >= FINAL_TOP_K:
            break

    log.info(f"Fetched {len(ordered)} parent docs after filter enforcement")
    return ordered


# ─────────────────────────────────────────
# 6. Main hybrid search function
# ─────────────────────────────────────────

def hybrid_search(
    query: str,
    filters: dict = None
) -> list[dict]:
    log.info(f"Hybrid search started | query: '{query}' | filters: {filters}")

    try:
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

        # Step 1: Semantic search
        semantic_docs = semantic_search(query, embeddings, filters)
        log.info(f"Semantic hits : {len(semantic_docs)}")

        # Step 2: Keyword search
        keyword_docs = keyword_search(query)
        log.info(f"Keyword hits  : {len(keyword_docs)}")

        # Step 3: RRF fusion
        fused_docs = reciprocal_rank_fusion(semantic_docs, keyword_docs)
        log.info(f"Fused hits    : {len(fused_docs)}")

        # Step 4: Small-to-Big — pass filters for enforcement
        parent_docs = fetch_parent_docs(fused_docs, filters)   # ← pass filters
        log.info(f"Final courses : {len(parent_docs)}")

        if not parent_docs:
            log.warning("Hybrid search returned no results")
            return []

        log.info("Hybrid search complete")
        return parent_docs

    except Exception as e:
        log.error(f"Hybrid search failed: {e}")
        raise