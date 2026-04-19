"""
CodingTaskCreatorAgent: Creates lesson-aligned coding exercises and test cases.

Responsibilities:
- Decide whether coding tasks are appropriate for the current topic
- Generate beginner-friendly coding exercises with starter code
- Produce test cases for server-side validation
"""

from typing import Any, Dict, List
import logging
import re

from ..base import BaseAgent
from ..config import ContentLevel

logger = logging.getLogger(__name__)


PROGRAMMING_KEYWORDS = {
    "code",
    "coding",
    "programming",
    "algorithm",
    "algorithms",
    "data structure",
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "go",
    "rust",
    "sql",
    "api",
    "backend",
    "frontend",
    "debug",
    "compiler",
    "runtime",
    "function",
    "loop",
    "recursion",
    "class",
    "object",
    "oop",
}

NON_PROGRAMMING_HINTS = {
    "history",
    "economics",
    "literature",
    "philosophy",
    "geography",
    "politics",
    "sociology",
    "anthropology",
    "psychology",
    "biology",
    "chemistry",
    "physics",
    "art",
    "music",
}

LANGUAGE_ID_BY_NAME = {
    "python": 71,
    "javascript": 63,
    "java": 62,
    "cpp": 54,
    "c++": 54,
}


class CodingTaskCreatorAgent(BaseAgent):
    """Generate coding tasks only when the topic is programming-related."""

    def __init__(self):
        super().__init__(name="CodingTaskCreatorAgent", timeout=35)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        topic = input_data.get("topic", "")
        subject = input_data.get("subject", "")
        subtopics = input_data.get("subtopics", [])
        learning_objectives = input_data.get("learning_objectives", [])
        difficulty = input_data.get("difficulty", ContentLevel.INTERMEDIATE)
        max_tasks = max(1, min(int(input_data.get("max_tasks", 2)), 5))
        decision_mode = str(input_data.get("decision_mode", "auto")).lower()

        if decision_mode == "skip":
            include_coding = False
            decision_reason = "Coding generation skipped by decision mode."
        elif decision_mode == "force":
            include_coding = True
            decision_reason = "Coding generation forced by decision mode."
        else:
            include_coding, decision_reason = self._should_include_coding(
                topic=topic,
                subject=subject,
                subtopics=subtopics,
                learning_objectives=learning_objectives,
            )

        if not include_coding:
            return {
                "include_coding_exercises": False,
                "decision_reason": decision_reason,
                "coding_tasks": [],
                "total_tasks": 0,
                "quality_score": 1.0,
                "difficulty": difficulty,
            }

        language = self._resolve_language(topic=topic, subject=subject, subtopics=subtopics)
        language_id = LANGUAGE_ID_BY_NAME.get(language, 71)

        tasks = [
            self._build_task(
                topic=topic,
                subtopic=subtopics[i % len(subtopics)] if subtopics else topic,
                difficulty=difficulty,
                language=language,
                language_id=language_id,
                index=i + 1,
            )
            for i in range(max_tasks)
        ]

        return {
            "include_coding_exercises": True,
            "decision_reason": decision_reason,
            "coding_tasks": tasks,
            "total_tasks": len(tasks),
            "quality_score": 0.85,
            "difficulty": difficulty,
            "language": language,
            "language_id": language_id,
        }

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        if "topic" not in input_data:
            raise ValueError("Missing required field: topic")
        if "subtopics" not in input_data:
            raise ValueError("Missing required field: subtopics")
        return True

    def _should_include_coding(
        self,
        topic: str,
        subject: str,
        subtopics: List[str],
        learning_objectives: List[str],
    ) -> tuple[bool, str]:
        text = " ".join(
            [topic, subject, " ".join(subtopics), " ".join(learning_objectives)]
        ).lower()

        keyword_hits = sum(1 for kw in PROGRAMMING_KEYWORDS if kw in text)
        non_programming_hits = sum(1 for kw in NON_PROGRAMMING_HINTS if kw in text)

        include_coding = keyword_hits > 0 and keyword_hits >= non_programming_hits
        if include_coding:
            return True, "Coding keywords detected; exercises are relevant for this lesson."
        return False, "Topic appears non-programming; coding exercises were skipped."

    def _resolve_language(self, topic: str, subject: str, subtopics: List[str]) -> str:
        text = " ".join([topic, subject, " ".join(subtopics)]).lower()

        if "javascript" in text or "js" in text:
            return "javascript"
        if "java" in text and "javascript" not in text:
            return "java"
        if "c++" in text or "cpp" in text:
            return "cpp"
        if "python" in text:
            return "python"

        return "python"

    def _slug(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
        return cleaned.strip("_") or "lesson"

    def _build_task(
        self,
        topic: str,
        subtopic: str,
        difficulty: ContentLevel,
        language: str,
        language_id: int,
        index: int,
    ) -> Dict[str, Any]:
        if language == "javascript":
            starting_code = (
                "const fs = require(\"fs\");\n\n"
                "function solve(rawInput) {\n"
                "  // TODO: implement here\n"
                "  const normalized = rawInput.trim();\n"
                "  return normalized.toUpperCase();\n"
                "}\n\n"
                "const input = fs.readFileSync(0, \"utf8\");\n"
                "const output = solve(input);\n"
                "process.stdout.write(String(output));\n"
            )
            solution_code = (
                "const fs = require(\"fs\");\n\n"
                "function solve(rawInput) {\n"
                "  const normalized = rawInput.trim();\n"
                "  return normalized.toUpperCase();\n"
                "}\n\n"
                "const input = fs.readFileSync(0, \"utf8\");\n"
                "const output = solve(input);\n"
                "process.stdout.write(String(output));\n"
            )
        elif language == "java":
            starting_code = (
                "import java.io.BufferedReader;\n"
                "import java.io.InputStreamReader;\n"
                "import java.util.stream.Collectors;\n\n"
                "public class Main {\n"
                "    static String solve(String rawInput) {\n"
                "        // TODO: implement here\n"
                "        String normalized = rawInput.trim();\n"
                "        return normalized.toUpperCase();\n"
                "    }\n\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n"
                "        String input = reader.lines().collect(Collectors.joining(\"\\n\"));\n"
                "        System.out.print(solve(input));\n"
                "    }\n"
                "}\n"
            )
            solution_code = (
                "import java.io.BufferedReader;\n"
                "import java.io.InputStreamReader;\n"
                "import java.util.stream.Collectors;\n\n"
                "public class Main {\n"
                "    static String solve(String rawInput) {\n"
                "        String normalized = rawInput.trim();\n"
                "        return normalized.toUpperCase();\n"
                "    }\n\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n"
                "        String input = reader.lines().collect(Collectors.joining(\"\\n\"));\n"
                "        System.out.print(solve(input));\n"
                "    }\n"
                "}\n"
            )
        elif language == "cpp":
            starting_code = (
                "#include <bits/stdc++.h>\n"
                "using namespace std;\n\n"
                "string solve(const string& rawInput) {\n"
                "    // TODO: implement here\n"
                "    string normalized = rawInput;\n"
                "    auto is_space = [](unsigned char ch) { return std::isspace(ch) != 0; };\n"
                "    while (!normalized.empty() && is_space((unsigned char)normalized.back())) normalized.pop_back();\n"
                "    size_t left = 0;\n"
                "    while (left < normalized.size() && is_space((unsigned char)normalized[left])) left++;\n"
                "    normalized = normalized.substr(left);\n"
                "    for (char& ch : normalized) ch = (char)toupper((unsigned char)ch);\n"
                "    return normalized;\n"
                "}\n\n"
                "int main() {\n"
                "    ios::sync_with_stdio(false);\n"
                "    cin.tie(nullptr);\n\n"
                "    string input((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());\n"
                "    cout << solve(input);\n"
                "    return 0;\n"
                "}\n"
            )
            solution_code = (
                "#include <bits/stdc++.h>\n"
                "using namespace std;\n\n"
                "string solve(const string& rawInput) {\n"
                "    string normalized = rawInput;\n"
                "    auto is_space = [](unsigned char ch) { return std::isspace(ch) != 0; };\n"
                "    while (!normalized.empty() && is_space((unsigned char)normalized.back())) normalized.pop_back();\n"
                "    size_t left = 0;\n"
                "    while (left < normalized.size() && is_space((unsigned char)normalized[left])) left++;\n"
                "    normalized = normalized.substr(left);\n"
                "    for (char& ch : normalized) ch = (char)toupper((unsigned char)ch);\n"
                "    return normalized;\n"
                "}\n\n"
                "int main() {\n"
                "    ios::sync_with_stdio(false);\n"
                "    cin.tie(nullptr);\n\n"
                "    string input((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());\n"
                "    cout << solve(input);\n"
                "    return 0;\n"
                "}\n"
            )
        else:
            starting_code = (
                "import sys\n\n"
                "def solve(raw_input: str) -> str:\n"
                "    # TODO: implement here\n"
                "    normalized = raw_input.strip()\n"
                "    return normalized.upper()\n\n"
                "if __name__ == \"__main__\":\n"
                "    data = sys.stdin.read()\n"
                "    sys.stdout.write(solve(data))\n"
            )
            solution_code = (
                "import sys\n\n"
                "def solve(raw_input: str) -> str:\n"
                "    normalized = raw_input.strip()\n"
                "    return normalized.upper()\n\n"
                "if __name__ == \"__main__\":\n"
                "    data = sys.stdin.read()\n"
                "    sys.stdout.write(solve(data))\n"
            )

        test_cases = [
            {"input": "hello", "expected_output": "HELLO", "is_hidden": False},
            {"input": "  world  ", "expected_output": "WORLD", "is_hidden": False},
            {"input": f" {topic[:20]} ", "expected_output": topic[:20].upper(), "is_hidden": True},
        ]

        return {
            "title": f"{subtopic or topic} Coding Task {index}",
            "language": language,
            "language_id": language_id,
            "instructions": (
                "Read raw text from stdin, trim leading/trailing whitespace, convert it to uppercase, "
                "and print the final string to stdout."
            ),
            "description": (
                f"Implement a complete program for {subtopic or topic}. "
                "Use stdin/stdout format like competitive programming platforms."
            ),
            "starting_code": starting_code,
            "solution_code": solution_code,
            "test_cases": test_cases,
            "hints": [
                "Read all text from stdin so your program works with spaces and multiple lines.",
                "Normalize by trimming whitespace first, then convert the full string to uppercase.",
            ],
            "difficulty": str(getattr(difficulty, "value", difficulty)),
        }
