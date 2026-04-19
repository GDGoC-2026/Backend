import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.schemas.knowledge import (
    NoteIngestRequest,
    NoteIngestResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    GraphDataResponse,
    IngestStatusResponse,
)
from Backend.services.formatter_agent import format_notes
from Backend.services.lightrag_service import get_lightrag_service
from Backend.workers.ingestion_tasks import ingest_lightrag_content


router = APIRouter()


@router.post(
    "/ingest",
    response_model=NoteIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw notes into knowledge graph"
)
async def ingest_notes(
    request: NoteIngestRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """
    Process raw notes through Formatter Agent and ingest into LightRAG.
    
    Flow:
    1. Receive raw notes from user
    2. Format and enhance using Gemini Formatter Agent
    3. Ingest formatted content into LightRAG knowledge graph
    4. Return formatted content for user review
    """
    try:
        # Step 1: Format raw notes using Gemini
        formatted_content = await format_notes(
            raw_content=request.content,
            title=request.title
        )
        
        # Step 2: Ingest into LightRAG
        use_background = os.getenv("LIGHTRAG_INGEST_USE_BACKGROUND", "false").lower() in {
            "1",
            "true",
            "yes",
        }

        if use_background:
            try:
                task = ingest_lightrag_content.delay(str(current_user.id), formatted_content)
                response.status_code = status.HTTP_202_ACCEPTED

                return NoteIngestResponse(
                    message=f"Notes formatted. Ingestion queued (task_id={task.id})",
                    formatted_content=formatted_content,
                    original_content=request.content,
                )
            except Exception:
                # If queue dispatch fails, gracefully fall back to synchronous ingestion.
                pass

        lightrag_service = get_lightrag_service()
        await lightrag_service.ingest_content(
            user_id=current_user.id,
            content=formatted_content,
        )
        
        # Step 3: Return response
        return NoteIngestResponse(
            message="Notes successfully formatted and ingested",
            formatted_content=formatted_content,
            original_content=request.content
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing notes: {str(e)}"
        )


@router.post(
    "/query",
    response_model=KnowledgeQueryResponse,
    summary="Query knowledge graph"
)
async def query_knowledge(
    request: KnowledgeQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Query the user's knowledge graph using LightRAG.
    
    Supported modes:
    - `local`: Search local context only
    - `global`: Search entire graph with global context
    - `hybrid`: Combine local and global for best results
    - `mix`: Mix mode with custom parameters
    """
    try:
        lightrag_service = get_lightrag_service()
        answer = await lightrag_service.query_knowledge(
            user_id=current_user.id,
            question=request.question,
            mode=request.mode
        )
        
        return KnowledgeQueryResponse(
            answer=answer,
            mode=request.mode
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying knowledge: {str(e)}"
        )


@router.get(
    "/graph",
    response_model=GraphDataResponse,
    summary="Get graph data for visualization"
)
async def get_graph(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the complete knowledge graph for the user.
    
    Returns nodes and edges in JSON format suitable for visualization
    with libraries like React Flow, D3.js, or vis.js.
    """
    try:
        lightrag_service = get_lightrag_service()
        graph_data = lightrag_service.get_graph_data(user_id=current_user.id)
        
        return GraphDataResponse(
            nodes=graph_data["nodes"],
            edges=graph_data["edges"]
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving graph: {str(e)}"
        )


@router.delete(
    "/graph",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user's knowledge graph"
)
async def delete_graph(
    current_user: User = Depends(get_current_user),
):
    """
    Delete the user's entire knowledge graph and stored data.
    
    This action is irreversible. The knowledge base will be reset.
    """
    try:
        lightrag_service = get_lightrag_service()
        success = lightrag_service.delete_graph(user_id=current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete graph"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting graph: {str(e)}"
        )


@router.get(
    "/ingest-status",
    response_model=IngestStatusResponse,
    summary="Get ingestion status for notes and graph"
)
async def get_ingest_status(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve ingestion pipeline status for the current user,
    including counts and per-document processing state.
    """
    try:
        lightrag_service = get_lightrag_service()
        status_data = lightrag_service.get_ingest_status(user_id=current_user.id)
        return IngestStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving ingest status: {str(e)}"
        )
