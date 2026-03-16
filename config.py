import os
from dotenv import load_dotenv

load_dotenv()

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Models ---
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL       = "gpt-4o"

# --- Qdrant (local file mode) ---
QDRANT_PATH             = "./storage/qdrant_db"
CHILDREN_COLLECTION     = "courses_children"
PARENTS_COLLECTION      = "courses_parents"
VECTOR_SIZE             = 1536

# --- BM25 ---
BM25_INDEX_PATH = "./storage/bm25_index.pkl"

# --- Data ---
DATA_PATH = "./data/coursera_course_dataset_v3_cleaned.csv"

# --- CSV field mapping (your actual column names → code names) ---
FIELD_MAP = {
    "unnamed: 0":               "row_index",          # ← drop this, just an index
    "title":                    "course_name",
    "organization":             "organization",
    "skills":                   "skills",
    "ratings":                  "rating",
    "course_url":               "course_url",
    "course_students_enrolled": "students_enrolled",
    "course_description":       "description",
    "review count":             "review_count",        # ← fixed (single, not plural)
    "difficulty":               "difficulty",
    "type":                     "course_type",         # ← new
    "duration":                 "duration"             # ← new
}  

# --- Retrieval ---
TOP_K           = 20
FINAL_TOP_K     = 10

# --- Ensemble weights ---
SEMANTIC_WEIGHT = 0.8
KEYWORD_WEIGHT  = 0.2