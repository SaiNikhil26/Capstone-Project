from qdrant_client import QdrantClient
from config import QDRANT_PATH, CHILDREN_COLLECTION, PARENTS_COLLECTION

client = QdrantClient(path=QDRANT_PATH)

# Collection stats
for name in [CHILDREN_COLLECTION, PARENTS_COLLECTION]:
    info = client.get_collection(name)
    print(f"\nCollection : {name}")
    print(f"Points     : {info.points_count}")

# Browse first 3 parent records
print("\n--- Sample Parent Records ---")
results = client.scroll(
    collection_name=PARENTS_COLLECTION,
    limit=3,
    with_payload=True,
    with_vectors=False
)
for point in results[0]:
    payload = point.payload
    print(f"\nCourse ID    : {payload.get('course_id')}")
    print(f"Course       : {payload.get('course_name')}")
    print(f"Org          : {payload.get('organization')}")
    print(f"Difficulty   : {payload.get('difficulty')}")
    print(f"Type         : {payload.get('course_type')}")
    print(f"Duration     : {payload.get('duration')}")
    print(f"Rating       : {payload.get('rating')}")
    print(f"Reviews      : {payload.get('review_count')}")
    print(f"Students     : {payload.get('students_enrolled')}")
    print(f"URL          : {payload.get('course_url')}")
    print(f"Skills       : {payload.get('skills')}")
    print(f"Content      : {payload.get('page_content')}")   # ← full embedded text including description
    print("-" * 60)

client.close()