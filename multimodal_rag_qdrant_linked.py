
# Multimodal RAG Prototype with Qdrant and OpenCLIP (Linked Image-Text Pairs)

import torch
import open_clip
from PIL import Image
from torchvision import transforms
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from uuid import uuid4
import os

# --- Config ---
COLLECTION_NAME = "multimodal_rag"
device = "cuda" if torch.cuda.is_available() else "cpu"

# --- Initialize Qdrant ---
client = QdrantClient(":memory:")  # use Qdrant docker or cloud if preferred
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=512, distance=Distance.COSINE),
)

# --- Load OpenCLIP model ---
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
tokenizer = open_clip.get_tokenizer("ViT-B-32")
model.to(device)

# --- Embedding Functions ---
def embed_text(text: str):
    tokens = tokenizer([text]).to(device)
    with torch.no_grad():
        return model.encode_text(tokens).cpu().numpy()[0]

def embed_image(image_path: str):
    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        return model.encode_image(image).cpu().numpy()[0]

# --- Upload Function ---
def upload_embedding(vector, metadata):
    point = PointStruct(
        id=str(uuid4()),
        vector=vector,
        payload=metadata
    )
    client.upsert(collection_name=COLLECTION_NAME, points=[point])

# --- Search Function ---
def search(query_vector, top_k=5):
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    return results

# --- Retrieve Linked Pair by pair_id ---
def retrieve_linked_items(pair_id):
    results = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[FieldCondition(key="pair_id", match=MatchValue(value=pair_id))]
        ),
        limit=10
    )
    return results[0]  # first element is list of points

# --- Example Usage ---

# Upload text and image as linked pair
examples = [
    {
        "image_path": "insulated_stick.jpg",
        "text_desc": "Image of an insulated stick that workers are required to use when working on power lines during earthing and short-circuiting procedures."
    },
    {
        "image_path": "helmet.jpg",
        "text_desc": "Personal Protection Equipment for power lines workers to protect themselves against electric rist as well as fall. This is a type II helmet, that you can also place a voltage detector on."
    }
]

for example in examples:
    if os.path.exists(example["image_path"]):
        pair_id = str(uuid4())
        
        # Embed and upload text
        text_vector = embed_text(example["text_desc"])
        upload_embedding(text_vector, {
            "modality": "text",
            "pair_id": pair_id,
            "description": example["text_desc"]
        })

        # Embed and upload image
        image_vector = embed_image(example["image_path"])
        upload_embedding(image_vector, {
            "modality": "image",
            "pair_id": pair_id,
            "description": f"Image for: {example['text_desc']}"
        })
    else:
        print(f"Missing image: {example['image_path']}")

# Now test a retrieval with text query
#query = "Power lines stick"  # should match the retriever
#query_vec = embed_text(query)
#results = search(query_vec, top_k=1)  # just return 1 result

# Query with an image instead of text
query_image_path = "query_image.jpg"  # use one of your test images
if os.path.exists(query_image_path):
    query_vec = embed_image(query_image_path)
    results = search(query_vec, top_k=1)

if results:
    top_result = results[0]
    print(f"Top result: {top_result.payload} (score: {top_result.score:.3f})")

    # Get the linked items (both image and text) using shared pair_id
    pair_id = top_result.payload.get("pair_id")
    print("Retrieving linked items for pair_id:", pair_id)

    linked_items = retrieve_linked_items(pair_id)
    for item in linked_items:
        print(" ↳ Linked:", item.payload)
else:
    print("No results found.")

