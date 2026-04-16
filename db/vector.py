from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from Backend.core.config import settings


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
