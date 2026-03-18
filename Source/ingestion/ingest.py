import os
import sys
import pickle
import pandas as pd

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    EMBEDDING_MODEL,
    QDRANT_PATH,
    CHILDREN_COLLECTION,
    PARENTS_COLLECTION,
    VECTOR_SIZE,
    BM25_INDEX_PATH,
    DATA_PATH,
    FIELD_MAP
)
from logger import get_logger

log = get_logger("ingest")


# ─────────────────────────────────────────
# 1. Load & remap CSV
# ─────────────────────────────────────────

def load_data(path: str) -> pd.DataFrame:
    log.info(f"Loading data from: {path}")

    df = pd.read_csv(path)
    log.debug(f"Raw shape: {df.shape} | Columns: {list(df.columns)}")

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    log.debug(f"Normalized columns: {list(df.columns)}")

    # Rename columns to internal names using FIELD_MAP
    df = df.rename(columns=FIELD_MAP)
    log.debug(f"Remapped columns: {list(df.columns)}")

    # Drop the unnamed index column if present
    if "row_index" in df.columns:
        df = df.drop(columns=["row_index"])
        log.debug("Dropped row_index column")

    # Add stable course_id
    df["course_id"] = [f"C{str(i+1).zfill(3)}" for i in range(len(df))]
    log.debug("Generated course_id column: C001, C002, ...")

    # Type normalization
    df["rating"]            = pd.to_numeric(df["rating"], errors="coerce").fillna(0.0)
    df["review_count"]      = pd.to_numeric(df["review_count"], errors="coerce").fillna(0)
    df["students_enrolled"] = pd.to_numeric(df["students_enrolled"], errors="coerce").fillna(0)
    df["course_type"]       = df["course_type"].fillna("Not specified")
    df["duration"]          = df["duration"].fillna("Not specified")

    log.info(f"Loaded {len(df)} courses successfully")
    log.debug(f"Sample record:\n{df.iloc[0].to_dict()}")
    return df


# ─────────────────────────────────────────
# 2. Build LangChain Documents
# ─────────────────────────────────────────

def build_parent_doc(row) -> Document:
    """
    Document-Specific chunking — full composite chunk per course.
    This is what GPT-4o reasons over (Small-to-Big: the 'Big').
    """
    text = f"""Course: {row['course_name']}
Provider: {row['organization']}
Level: {row['difficulty']}
Type: {row['course_type']}
Duration: {row['duration']}
Skills: {row['skills']}
Description: {row['description']}
Rating: {row['rating']} | Students enrolled: {row['students_enrolled']}""".strip()

    return Document(
        page_content=text,
        metadata={
            "course_id":         row["course_id"],
            "course_name":       row["course_name"],
            "organization":      row["organization"],
            "difficulty":        row["difficulty"],
            "course_type":       row["course_type"],
            "duration":          row["duration"],
            "rating":            float(row["rating"]),
            "review_count":      int(row["review_count"]),
            "students_enrolled": int(row["students_enrolled"]),
            "course_url":        row["course_url"],
            "skills":            row["skills"],
            "type":              "parent"
        }
    )


def build_child_docs(row) -> list[Document]:
    """
    Hierarchical chunking — three focused child chunks per course.
    These are what get searched (Small-to-Big: the 'Small').
    Each carries course_id as parent_id to look up full record after match.
    """
    parent_id = row["course_id"]

    chunks = [
        (
            f"Course: {row['course_name']} by {row['organization']} — {row['difficulty']} level, {row['course_type']}, Duration: {row['duration']}",
            "identity"
        ),
        (
            f"Skills taught in this course: {row['skills']}",
            "skills"
        ),
        (
            f"Course description: {row['description']}",
            "description"
        ),
    ]

    docs = []
    for text, chunk_type in chunks:
        docs.append(Document(
            page_content=text,
            metadata={
                "parent_id":         parent_id,
                "chunk_type":        chunk_type,
                "course_name":       row["course_name"],
                "organization":      row["organization"],
                "difficulty":        row["difficulty"],
                "course_type":       row["course_type"],
                "duration":          row["duration"],
                "rating":            float(row["rating"]),
                "review_count":      int(row["review_count"]),
                "students_enrolled": int(row["students_enrolled"]),
                "course_url":        row["course_url"],
                "skills":            row["skills"],
            }
        ))
    return docs


def build_bm25_doc(row) -> Document:
    """
    Keyword-optimized doc per course for BM25 index.
    Concentrates all searchable terms into one document
    so BM25 scores them as a single strong match.
    """
    text = f"""
{row['course_name']}
{row['organization']}
{row['difficulty']}
{row['course_type']}
{row['duration']}
{row['skills']}
{row['description']}
    """.strip()

    return Document(
        page_content=text,
        metadata={
            "parent_id":         row["course_id"],
            "course_name":       row["course_name"],
            "organization":      row["organization"],
            "difficulty":        row["difficulty"],
            "course_type":       row["course_type"],
            "duration":          row["duration"],
            "rating":            float(row["rating"]),
            "review_count":      int(row["review_count"]),
            "students_enrolled": int(row["students_enrolled"]),
            "course_url":        row["course_url"],
            "skills":            row["skills"],
        }
    )


def build_all_documents(df: pd.DataFrame):
    log.info("Building LangChain Documents from dataframe")

    parent_docs = []
    child_docs  = []
    bm25_docs   = []

    for _, row in df.iterrows():
        parent_docs.append(build_parent_doc(row))
        child_docs.extend(build_child_docs(row))
        bm25_docs.append(build_bm25_doc(row))

    log.info(
        f"Built {len(parent_docs)} parent docs | "
        f"{len(child_docs)} child chunks | "
        f"{len(bm25_docs)} BM25 docs"
    )
    return parent_docs, child_docs, bm25_docs


# ─────────────────────────────────────────
# 3. Initialize Qdrant collections
# ─────────────────────────────────────────

def init_qdrant_collections(client: QdrantClient):
    existing = [c.name for c in client.get_collections().collections]
    log.debug(f"Existing Qdrant collections: {existing}")

    for name in [CHILDREN_COLLECTION, PARENTS_COLLECTION]:
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
            log.info(f"Created Qdrant collection: '{name}'")
        else:
            log.info(f"Collection already exists, skipping: '{name}'")


# ─────────────────────────────────────────
# 4. Store in Qdrant
# ─────────────────────────────────────────

def store_in_qdrant(
    parent_docs: list[Document],
    child_docs:  list[Document],
    embeddings:  OpenAIEmbeddings,
    client:      QdrantClient
):
    # ── Helper: embed in batches + upsert with full payload ──
    def upsert_docs(docs: list[Document], collection_name: str, batch_size: int = 100):
        total = len(docs)
        for i in range(0, total, batch_size):
            batch = docs[i:i + batch_size]
            texts = [doc.page_content for doc in batch]

            # Embed batch
            vectors = embeddings.embed_documents(texts)

            # Build points with full metadata as payload
            points = []
            for doc, vector in zip(batch, vectors):
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "page_content": doc.page_content,
                        "metadata": doc.metadata          # ← LangChain expects nested metadata
                    }
                ))

            client.upsert(
                collection_name=collection_name,
                points=points
            )
            log.info(f"Upserted batch {i // batch_size + 1} / {(total + batch_size - 1) // batch_size} → '{collection_name}'")

    # Store child chunks
    log.info(f"Embedding {len(child_docs)} child chunks — this may take a moment...")
    try:
        upsert_docs(child_docs, CHILDREN_COLLECTION)
        log.info(f"Stored {len(child_docs)} child chunks → '{CHILDREN_COLLECTION}'")
    except Exception as e:
        log.error(f"Failed to store child chunks: {e}")
        raise

    # Store parent docs
    log.info(f"Storing {len(parent_docs)} parent docs...")
    try:
        upsert_docs(parent_docs, PARENTS_COLLECTION)
        log.info(f"Stored {len(parent_docs)} parent docs → '{PARENTS_COLLECTION}'")
    except Exception as e:
        log.error(f"Failed to store parent docs: {e}")
        raise

# ─────────────────────────────────────────
# 5. Build & save BM25 index
# ─────────────────────────────────────────

def build_bm25_index(bm25_docs: list[Document]):
    os.makedirs(os.path.dirname(BM25_INDEX_PATH), exist_ok=True)
    log.info(f"Building BM25 index over {len(bm25_docs)} keyword docs")

    try:
        bm25_retriever = BM25Retriever.from_documents(bm25_docs)
        bm25_retriever.k = 10

        with open(BM25_INDEX_PATH, "wb") as f:
            pickle.dump(bm25_retriever, f)

        log.info(f"BM25 index saved → {BM25_INDEX_PATH}")
    except Exception as e:
        log.error(f"Failed to build BM25 index: {e}")
        raise


# ─────────────────────────────────────────
# 6. Main ingestion pipeline
# ─────────────────────────────────────────

def ingest():
    log.info("=== Ingestion pipeline started ===")

    try:
        df = load_data(DATA_PATH)
        parent_docs, child_docs, bm25_docs = build_all_documents(df)

        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        log.info(f"Initialized embeddings: {EMBEDDING_MODEL}")

        os.makedirs(QDRANT_PATH, exist_ok=True)
        client = QdrantClient(path=QDRANT_PATH)
        log.info(f"Qdrant local client initialized at: {QDRANT_PATH}")

        init_qdrant_collections(client)

        # Pass client directly — no URL/location confusion
        store_in_qdrant(parent_docs, child_docs, embeddings, client)

        build_bm25_index(bm25_docs)

        log.info("=== Ingestion pipeline complete ===")
        log.info(f"Courses indexed  : {len(df)}")
        log.info(f"Child chunks     : {len(child_docs)}")
        log.info(f"BM25 docs        : {len(bm25_docs)}")
        log.info(f"Qdrant path      : {QDRANT_PATH}")
        log.info(f"BM25 index path  : {BM25_INDEX_PATH}")

    except Exception as e:
        log.critical(f"Ingestion pipeline failed: {e}")
        raise


if __name__ == "__main__":
    ingest()