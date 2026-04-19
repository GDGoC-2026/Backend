import asyncio
import os
from typing import Any

import httpx


class JudgeController:
    def __init__(self):
        configured_url = os.getenv("JUDGE0_URL") or os.getenv("JUDGE0_API_URL")
        candidates = [
            configured_url,
            "http://judge-server:2358",
            "http://localhost:2358",
            "http://127.0.0.1:2358",
        ]
        self.judge0_urls = []
        for candidate in candidates:
            if candidate and candidate not in self.judge0_urls:
                self.judge0_urls.append(candidate)

        self.judge0_url = self.judge0_urls[0]
        self.poll_interval_seconds = 0.5
        self.max_poll_attempts = 120

    async def _submit_and_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None

        for judge0_url in self.judge0_urls:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{judge0_url}/submissions?base64_encoded=false&wait=false",
                        json=payload,
                    )
                    response.raise_for_status()
                    token = response.json()["token"]

                    for _ in range(self.max_poll_attempts):
                        result_response = await client.get(
                            f"{judge0_url}/submissions/{token}?base64_encoded=false"
                        )
                        result_response.raise_for_status()
                        result_data = result_response.json()

                        status_id = result_data.get("status", {}).get("id")
                        # Status 1 is 'In Queue', 2 is 'Processing'
                        if status_id not in [1, 2]:
                            return result_data

                        await asyncio.sleep(self.poll_interval_seconds)

                last_error = TimeoutError(f"Judge0 execution timed out on {judge0_url}")
            except Exception as exc:
                last_error = exc
                continue

        raise RuntimeError(
            f"Judge0 unavailable on configured hosts ({', '.join(self.judge0_urls)}): {last_error}"
        ) from last_error

    async def execute_submission(
        self,
        source_code: str,
        language_id: int,
        stdin: str | None = None,
        expected_output: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_code": source_code,
            "language_id": language_id,
        }
        if stdin is not None:
            payload["stdin"] = stdin
        if expected_output is not None:
            payload["expected_output"] = expected_output

        return await self._submit_and_wait(payload)

    async def execute_code(self, source_code: str, language_id: int, expected_output: str) -> dict[str, Any]:
        """Backward-compatible wrapper used by legacy execution endpoint."""
        return await self.execute_submission(
            source_code=source_code,
            language_id=language_id,
            expected_output=expected_output,
        )

    async def run_code(
        self,
        source_code: str,
        language_id: int,
        stdin: str | None = None,
    ) -> dict[str, Any]:
        """Run code without grading."""
        return await self.execute_submission(
            source_code=source_code,
            language_id=language_id,
            stdin=stdin,
        )

    async def evaluate_test_cases(
        self,
        source_code: str,
        language_id: int,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate source code against a list of test cases with normalized output comparison."""
        case_results: list[dict[str, Any]] = []
        passed_tests = 0

        async for case_result in self.iter_test_case_results(
            source_code=source_code,
            language_id=language_id,
            test_cases=test_cases,
        ):
            case_results.append(case_result)
            if bool(case_result.get("passed")):
                passed_tests += 1

        total_tests = len(case_results)
        all_passed = total_tests > 0 and passed_tests == total_tests

        status_label = "Accepted" if all_passed else "Wrong Answer"
        for result in case_results:
            if result.get("compile_output"):
                status_label = "Compilation Error"
                break
            if result.get("status") and str(result.get("status")).lower() not in {
                "accepted",
                "wrong answer",
            } and not result.get("passed", False):
                status_label = str(result.get("status"))
                break

        return {
            "passed": all_passed,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "status": status_label,
            "results": case_results,
        }

    async def iter_test_case_results(
        self,
        source_code: str,
        language_id: int,
        test_cases: list[dict[str, Any]],
    ):
        """Yield per-test-case evaluation results sequentially for real-time UX."""
        for index, case in enumerate(test_cases, start=1):
            input_text = str(case.get("input", ""))
            expected_output = str(case.get("expected_output", ""))
            is_hidden = bool(case.get("is_hidden", False))

            result = await self.execute_submission(
                source_code=source_code,
                language_id=language_id,
                stdin=input_text,
            )

            status_data = result.get("status", {})
            status_id = status_data.get("id")
            actual_output = (
                (result.get("stdout") or "").strip()
                if result.get("stdout") is not None
                else None
            )
            normalized_actual = (actual_output or "").strip()
            normalized_expected = expected_output.strip()
            execution_succeeded = status_id == 3
            passed = execution_succeeded and normalized_actual == normalized_expected

            yield {
                "index": index,
                "input": input_text,
                "expected_output": expected_output,
                "actual_output": actual_output,
                "passed": passed,
                "status": status_data.get("description"),
                "stderr": result.get("stderr"),
                "compile_output": result.get("compile_output"),
                "time": result.get("time"),
                "memory": result.get("memory"),
                "is_hidden": is_hidden,
            }
