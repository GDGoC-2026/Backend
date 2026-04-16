from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from Backend.core.config import settings
import logging

logger = logging.getLogger(__name__)


COLLECTION_NAME = "knowledge_chunks"


def init_milvus():
    connections.connect(
        alias="default", 
        uri=settings.milvus_uri
    )

    if not utility.has_collection(COLLECTION_NAME):
        fields = [
            # Primary key
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            # Metadata for isolation and referencing
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            # Vector field (Gemini models output 768 dimensions)
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)
        ]
        schema = CollectionSchema(fields=fields, description="User uploaded knowledge chunks")
        collection = Collection(name=COLLECTION_NAME, schema=schema)
        
        # Create an index for faster vector similarity search
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
    
    collection = Collection(COLLECTION_NAME)
    collection.load() # Load into memory for searching
    return collection


def disconnect_milvus():
    connections.disconnect("default")

def create_default_collections():
    """
    Create default Milvus collections for RAG:
    1. coding - For code snippets and programming tips
    2. english - For English language learning content
    """
    collections = ["coding", "english"]
    
    for collection_name in collections:
        if Collection.exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            continue
        
        # Define schema with fields: id, text embeddings, metadata
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=2048),  # JSON string
            FieldSchema(name="source_type", dtype=DataType.VARCHAR, max_length=50),  # user_note, tip, etc.
            FieldSchema(name="created_at", dtype=DataType.INT64),  # timestamp
            FieldSchema(name="user_id", dtype=DataType.INT64),  # for user-specific recommendations
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description=f"Collection for {collection_name} content RAG"
        )
        
        collection = Collection(name=collection_name, schema=schema)
        
        # Create index on embeddings for faster search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 200}
        }
        collection.create_index(field_name="embeddings", index_params=index_params)
        logger.info(f"Collection '{collection_name}' created successfully with HNSW index")

def get_collection(collection_name: str) -> Collection | None:
    """Get a collection by name"""
    if Collection.exists(collection_name):
        return Collection(collection_name)
    return None
