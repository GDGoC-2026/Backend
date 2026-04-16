from pydantic import BaseModel


class NoteIngestRequest(BaseModel):
    """Request schema for ingesting raw notes into LightRAG."""
    content: str
    title: str | None = None


class NoteIngestResponse(BaseModel):
    """Response schema after note ingestion and formatting."""
    message: str
    formatted_content: str
    original_content: str


class KnowledgeQueryRequest(BaseModel):
    """Request schema for querying the knowledge graph."""
    question: str
    mode: str = "hybrid"  # local | global | hybrid | mix


class KnowledgeQueryResponse(BaseModel):
    """Response schema for knowledge query results."""
    answer: str
    mode: str


class GraphNode(BaseModel):
    """Represents a node in the knowledge graph."""
    id: str
    label: str
    properties: dict = {}


class GraphEdge(BaseModel):
    """Represents an edge/relationship in the knowledge graph."""
    source: str
    target: str
    label: str
    properties: dict = {}


class GraphDataResponse(BaseModel):
    """Response schema for complete graph data visualization."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
