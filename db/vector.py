from pymilvus import connections
from Backend.core.config import settings

def connect_milvus():
    connections.connect(
        alias="default", 
        uri=settings.milvus_uri
    )

def disconnect_milvus():
    connections.disconnect("default")