from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from jose import JWTError, jwt
import json

from Backend.db.session import AsyncSessionLocal
from Backend.services.judge_controller import JudgeController
from Backend.services.gamification import GamificationEngine
from Backend.core.config import settings
from Backend.core.security import ALGORITHM
from Backend.models.user import User

router = APIRouter()
judge_controller = JudgeController()


async def _authenticate_websocket_user(websocket: WebSocket) -> User | None:
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


@router.websocket("/ws/execute")
async def websocket_endpoint(websocket: WebSocket):
    user = await _authenticate_websocket_user(websocket)
    if not user:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    user_id = str(user.id)

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
