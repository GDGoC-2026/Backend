from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json

from Backend.db.session import AsyncSessionLocal
from Backend.services.judge_controller import JudgeController
from Backend.services.gamification import GamificationEngine

router = APIRouter()
judge_controller = JudgeController()

@router.websocket("/ws/execute")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # In a production scenario, authenticate the user via token sent over WS here
    # user_id = await authenticate_ws(websocket)
    user_id = "placeholder_uuid_for_now" 

    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            
            source_code = data.get("source_code")
            language_id = data.get("language_id", 71) # e.g., 71 for Python, 54 for C++
            expected_output = data.get("expected_output")

            await websocket.send_json({"event": "status", "message": "Code submitted to sandbox..."})
            
            # Execute code
            result = await judge_controller.execute_code(source_code, language_id, expected_output)
            
            # Send execution result back to client
            await websocket.send_json({
                "event": "execution_result",
                "stdout": result.get("stdout"),
                "stderr": result.get("stderr"),
                "status": result.get("status", {}).get("description"),
                "time": result.get("time")
            })

            # Gamification Loop
            if result.get("status", {}).get("id") == 3: # 3 = Accepted / Passed
                async with AsyncSessionLocal() as db:
                    xp_update = await GamificationEngine.award_xp(db, user_id, amount=15)
                    streak_update = await GamificationEngine.update_streak(db, user_id)
                    
                    await websocket.send_json({
                        "event": "gamification_update",
                        "data": {**xp_update, **streak_update}
                    })

    except WebSocketDisconnect:
        print("Client disconnected from editor socket.")
    except Exception as e:
        await websocket.send_json({"event": "error", "message": str(e)})
