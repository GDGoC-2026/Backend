from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymilvus import Collection
# from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
# from langchain.schema import HumanMessage, SystemMessage

from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.core.config import settings

router = APIRouter()

# embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.gemini_api_key)
# llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=settings.gemini_api_key, temperature=0.2)

class ChatRequest(BaseModel):
    message: str

@router.post("/ask")
async def ask_copilot(req: ChatRequest, current_user: User = Depends(get_current_user)):
    pass
    # # 1. Embed the user's question
    # query_vector = embeddings.embed_query(req.message)
    
    # # 2. Vector Search in Milvus (Isolate by user_id)
    # collection = Collection("knowledge_chunks")
    # collection.load()
    
    # search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
    # results = collection.search(
    #     data=[query_vector],
    #     anns_field="embedding",
    #     param=search_params,
    #     limit=4,  # Retrieve the top 4 most relevant chunks
    #     expr=f'user_id == "{str(current_user.id)}"', # Critical: Security boundary
    #     output_fields=["text", "file_name"]
    # )
    
    # # 3. Construct Context from search results
    # context_blocks = []
    # sources = set()
    # for hits in results:
    #     for hit in hits:
    #         context_blocks.append(f"[{hit.entity.get('file_name')}]: {hit.entity.get('text')}")
    #         sources.add(hit.entity.get('file_name'))
            
    # compiled_context = "\n\n".join(context_blocks)
            
    # # 4. Generate Grounded Response
    # system_prompt = SystemMessage(content=f"""
    # You are an expert Socratic tutor and learning companion. Answer the user's question using ONLY the provided context from their uploaded personal notes. 
    # If the context does not contain the answer, gently state that the information isn't in their current notes, and encourage them to upload related materials.
    
    # --- CONTEXT FROM USER NOTES ---
    # {compiled_context}
    # """)
    
    # user_prompt = HumanMessage(content=req.message)
    
    # response = llm.invoke([system_prompt, user_prompt])
    
    # return {
    #     "reply": response.content, 
    #     "sources": list(sources)
    # }
