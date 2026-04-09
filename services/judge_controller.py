import httpx
import asyncio

class JudgeController:
    def __init__(self):
        self.judge0_url = "http://judge-server:2358" # Docker service name

    async def execute_code(self, source_code: str, language_id: int, expected_output: str) -> dict:
        """
        Sends code to Judge0 and polls for the result.
        """
        payload = {
            "source_code": source_code,
            "language_id": language_id,
            "expected_output": expected_output
        }

        async with httpx.AsyncClient() as client:
            # Submit submission
            response = await client.post(
                f"{self.judge0_url}/submissions?base64_encoded=false&wait=false",
                json=payload
            )
            response.raise_for_status()
            token = response.json()["token"]

            # Poll for results (Judge0 processes asynchronously)
            while True:
                result_response = await client.get(f"{self.judge0_url}/submissions/{token}?base64_encoded=false")
                result_data = result_response.json()
                
                status_id = result_data.get("status", {}).get("id")
                # Status 1 is 'In Queue', 2 is 'Processing'
                if status_id not in [1, 2]:
                    return result_data
                
                await asyncio.sleep(0.5)