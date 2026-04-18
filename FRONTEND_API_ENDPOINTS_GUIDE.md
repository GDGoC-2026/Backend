# Frontend API Endpoints Integration Guide

This document lists all currently available API endpoints and explains how each one should be consumed from the frontend.

## 1. Scope and assumptions

- Backend base URL during local development: `http://localhost:8000`
- API prefix: `/api/v1`
- Frontend repository currently has no implemented source files, so component names below are proposed integration targets.
- Most endpoints require `Authorization: Bearer <access_token>`.

## 2. Frontend foundation

### 2.1 API client baseline

Create one shared API client so all features behave consistently.

```ts
// src/shared/api/client.ts
const API_ORIGIN = import.meta.env.VITE_API_ORIGIN ?? "http://localhost:8000";
export const API_BASE = `${API_ORIGIN}/api/v1`;

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
```

### 2.2 Auth token handling

- Store `access_token` after login/register callback flow.
- Attach token to every protected endpoint.
- On `401`, clear auth state and redirect to login.

### 2.3 Real-time and streaming helpers

- Use `fetch` streaming (`ReadableStream`) for recommendation SSE endpoint.
- Use `WebSocket` for editor execution endpoint.
- Use `FormData` for markdown/document upload and lesson generation.

## 3. Endpoint catalog and frontend integration

Full path format in this section includes `/api/v1` unless explicitly stated otherwise.

---

## 3.1 System health

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `GET /health` (root, no `/api/v1`) | `SystemStatusBadge` in app shell | No auth, no body | Returns `{ "status": "ok" }`. Use for global backend online check before login. |

---

## 3.2 Auth endpoints (`/api/v1/auth`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/auth/register` | `RegisterForm` | JSON body: `{ email, password, full_name? }` | Returns `UserProfile`. After success, optionally auto-login flow by calling `/api/v1/auth/login`. |
| `POST /api/v1/auth/login` | `LoginForm` | JSON body: `{ email, password }` | Returns `{ access_token, token_type }`. Save token, hydrate user profile (`/api/v1/auth/me`), navigate to dashboard. |
| `GET /api/v1/auth/me` | `AuthProvider` bootstrap and `ProfileMenu` | Bearer token | Returns `UserProfile`. Run on app load to restore session. |
| `GET /api/v1/auth/google/login` | `OAuthButtons` (`Continue with Google`) | Browser redirect (do not call via XHR) | Trigger `window.location.href = API_ORIGIN + "/api/v1/auth/google/login"`. |
| `GET /api/v1/auth/google/callback` | `OAuthCallbackPage` | Redirect callback from OAuth provider | Returns token JSON. If using popup flow, parse token and `postMessage` to opener. |
| `GET /api/v1/auth/github/login` | `OAuthButtons` (`Continue with GitHub`) | Browser redirect | Same pattern as Google login endpoint. |
| `GET /api/v1/auth/github/callback` | `OAuthCallbackPage` | Redirect callback from OAuth provider | Returns token JSON. Handle like Google callback. |

Implementation detail:
- OAuth callback currently returns JSON token, not a redirect to frontend route. If you want cleaner UX, add a backend redirect-to-frontend enhancement.

---

## 3.3 User endpoints (`/api/v1/users`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `GET /api/v1/users/profile` | `AccountSettingsPage` | Bearer token | Returns `UserProfile`. Use for account details panel. |
| `PUT /api/v1/users/subscription` | `SubscriptionPlanSelector` | Bearer token, JSON body: `{ new_tier }` where tier is one of `freemium`, `pro`, `developer`, `enterprise` | Returns updated `UserProfile`. Immediately refresh feature flags (sandbox availability, etc.). |

---

## 3.4 Notifications endpoint (`/api/v1/notifications`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/notifications/subscribe` | `NotificationSettingsCard` + service worker registration | Bearer token, JSON body from Push API subscription: `{ endpoint, keys: { p256dh, auth } }` | Returns success message. Call only after user grants browser notification permission. |

---

## 3.5 Editor realtime endpoint (`/api/v1/editor`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `WEBSOCKET /api/v1/editor/ws/execute` | `LiveCodeEditorPanel` / `RealtimeRunner` | Open socket with token in query: `ws://host/api/v1/editor/ws/execute?token=<jwt>`; send payload `{ source_code, language_id, expected_output }` | Receive events: `status`, `execution_result`, `gamification_update`, `error`. Keep connection open while editor tab is active. |

WebSocket message example:

```json
{ "source_code": "print('hello')", "language_id": 71, "expected_output": "hello\n" }
```

---

## 3.6 Notes and folders endpoints (`/api/v1/notes`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `GET /api/v1/notes/graph-visualizer` | `KnowledgeGraphPanel` in notes workspace | Bearer token | Returns graph JSON for visualization (Neo4j-backed). |
| `POST /api/v1/notes/folders` | `FolderCreateModal` | Bearer token, JSON body: `{ name, parent_id? }` | Returns created folder. If parent provided, backend validates ownership. |
| `GET /api/v1/notes/folders` | `FolderTree` root loader | Bearer token | Returns root folders only (`parent_id == null`). |
| `GET /api/v1/notes/folders/{folder_id}` | `FolderDetailsDrawer` | Bearer token, path `folder_id` | Returns folder + `subfolders` + `notes` for tree expansion and list rendering. |
| `DELETE /api/v1/notes/folders/{folder_id}` | `FolderActionsMenu` | Bearer token, path `folder_id` | Returns `204`. Optimistically remove from UI, rollback on error. |
| `POST /api/v1/notes/upload` | `MarkdownUploadDialog` | Bearer token, `multipart/form-data`: `file` (`.md` only), optional query `folder_id` | Returns `202` + `task_id` + note object. Show "processing" state while background ingestion runs. |
| `GET /api/v1/notes` | `NotesList` | Bearer token, optional query `folder_id` | Returns notes list (filtered to folder or root-level notes). |
| `POST /api/v1/notes` | `NoteEditor` create action | Bearer token, JSON body: `{ title, content, folder_id? }` | Returns created note (`201`). If content is non-empty, backend triggers async ingestion automatically. |
| `PUT /api/v1/notes/{note_id}` | `NoteEditor` save action | Bearer token, JSON body partial: `{ title?, content?, folder_id? }` | Returns updated note. Sets `is_synced_with_graph=false` until background ingestion completes. |
| `GET /api/v1/notes/{note_id}` | `NoteDetailPage` | Bearer token, path `note_id` | Returns single note. |
| `DELETE /api/v1/notes/{note_id}` | `NoteActionsMenu` | Bearer token, path `note_id` | Returns `204`. Remove note from local cache/list. |

---

## 3.7 Knowledge graph endpoints (`/api/v1/knowledge`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/knowledge/ingest` | `KnowledgeIngestPanel` | Bearer token, JSON: `{ content, title? }` | Returns `201` (sync ingest) or `202` (queued ingest) with formatted content. Show formatted preview in UI. |
| `POST /api/v1/knowledge/query` | `KnowledgeQueryBox` | Bearer token, JSON: `{ question, mode }` where mode is `local`, `global`, `hybrid`, or `mix` | Returns `{ answer, mode }`. Render answer in rich text panel. |
| `GET /api/v1/knowledge/graph` | `KnowledgeGraphCanvas` | Bearer token | Returns `{ nodes, edges }` for graph libs (React Flow, D3, vis). |
| `DELETE /api/v1/knowledge/graph` | `DangerZoneResetKnowledge` | Bearer token | Returns `204`. Ask for destructive confirmation in frontend. |

---

## 3.8 Recommendation endpoints (`/api/v1/recommendations`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/recommendations/stream` | `InlineRecommendationPanel` in editor/writer | Bearer token, JSON: `{ content, content_type, user_context?, trigger_lines? }` | Returns SSE stream (`text/event-stream`). Parse `data:` lines and append chunks progressively. |
| `POST /api/v1/recommendations/add-to-rag` | `SaveInsightButton` / `RecommendationFeedback` | Bearer token, JSON: `{ content, content_type, metadata, source_type }` | Returns `{ success, message, content_id }`. Use after user accepts suggestion or saves note. |
| `GET /api/v1/recommendations/health` | `RecommendationStatusChip` | No auth required | Returns service readiness. Disable recommendation UI if unavailable. |

SSE parsing example:

```ts
async function streamRecommendations(token: string, payload: any, onChunk: (text: string) => void) {
  const res = await fetch(`${API_BASE}/recommendations/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const reader = res.body?.getReader();
  if (!reader) throw new Error("Missing stream body");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const eventText of events) {
      const line = eventText.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const payload = JSON.parse(line.replace("data: ", ""));
      if (payload.chunk) onChunk(payload.chunk);
    }
  }
}
```

---

## 3.9 Learning (flashcards) endpoints (`/api/v1/learning`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `GET /api/v1/learning` | `FlashcardListPage` | Bearer token, query: `limit`, `offset` | Returns user flashcards ordered by due date. |
| `POST /api/v1/learning` | `FlashcardCreateModal` | Bearer token, JSON: `{ front_content, back_content }` | Returns created flashcard. |
| `PUT /api/v1/learning/{card_id}` | `FlashcardEditor` | Bearer token, JSON: `{ front_content, back_content }` | Returns updated flashcard. |
| `DELETE /api/v1/learning/{card_id}` | `FlashcardCardActions` | Bearer token | Returns success message. |
| `GET /api/v1/learning/due` | `ReviewSessionPage` | Bearer token, query: `limit`, `offset` | Returns cards due for FSRS review now. |
| `POST /api/v1/learning/{card_id}/review` | `FlashcardReviewControls` | Bearer token, JSON: `{ grade }` where grade in `1..4` | Returns next due date + gamification updates. Use to drive review progress bar and XP toast. |

---

## 3.10 Gamification endpoints (`/api/v1/gamification`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `GET /api/v1/gamification/my-stats` | `XPBadge` and `StreakWidget` | Bearer token | Returns current user XP/level/streak stats (or default zero state). |
| `GET /api/v1/gamification/leaderboard` | `LeaderboardPage` | Bearer token (currently endpoint does not require current user data but keep auth consistency) | Returns top users by XP. Poll periodically or refresh on page focus. |

---

## 3.11 Judge endpoints (`/api/v1/judge`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/judge/execute` | `ExerciseCodeRunner` | Bearer token, JSON: `{ source_code, language_id, exercise_id }` | Executes against exercise expected output. Requires subscription tier `developer` or `enterprise`. |
| `POST /api/v1/judge/sessions` | `CodeAutosaveService` | Bearer token, JSON: `{ current_code, language_id, exercise_id?, coding_problem_id? }` | Upserts saved code. Exactly one of `exercise_id` or `coding_problem_id` must be provided. |
| `GET /api/v1/judge/sessions/{problem_id}` | `ResumeCodingBanner` | Bearer token, path `problem_id` | Returns saved session for generated coding problem. Use to prefill editor. |
| `PUT /api/v1/judge/sessions/{problem_id}` | `CodeAutosaveService` (targeted) | Bearer token, JSON: `{ current_code, language_id }` | Creates or updates coding-problem session by problem id. |

---

## 3.12 Chatbot endpoint (`/api/v1/chatbot`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/chatbot/ask` | `LearningCopilotChatPanel` | Bearer token, JSON: `{ message }` | Returns `{ reply, mode }`. Rejects empty messages; trim input client-side before submit. |

---

## 3.13 Documents endpoint (`/api/v1/documents`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/documents/upload` | `DocumentImportDialog` | Bearer token, `multipart/form-data`: `file` (`.pdf`, `.docx`, `.txt`), optional query `folder_id` | Returns `202` + `task_id` + created note-like document. Show queue/progress status and refresh notes list after completion. |

---

## 3.14 Quiz endpoints (`/api/v1/quiz`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/quiz/generate` | `QuizGeneratorForm` | Bearer token, JSON `QuizGenerationRequest`: topic/level/preferences/question types | Returns generated quiz (`quiz_id`, `questions`, distributions, quality metrics). Persist `quiz_id` in frontend state for retries. |
| `POST /api/v1/quiz/evaluate` | `QuizPlayerPage` submit action | Bearer token, JSON `QuizEvaluationRequest`: questions + answers + optional `quiz_id` and `source_lesson_id` | Returns scoring details, recommendations, and gamification payload. |
| `GET /api/v1/quiz/attempts` | `QuizHistoryTable` | Bearer token, query: `limit`, `offset`, optional `topic`, `quiz_id`, `retries_only` | Returns paged attempt summaries for user history UI. |
| `GET /api/v1/quiz/attempts/{attempt_id:uuid}` | `QuizAttemptDetailPage` | Bearer token | Returns full details including per-question results. |
| `GET /api/v1/quiz/retries/{quiz_id}` | `QuizProgressTimeline` | Bearer token | Returns all attempts for same quiz id in chronological attempt order. |
| `GET /api/v1/quiz/analytics` | `QuizAnalyticsDashboard` | Bearer token, optional query `topic` | Returns aggregate analytics, pass rates, improvements, XP totals. |
| `GET /api/v1/quiz/analytics/lessons/{source_lesson_id:uuid}` | `LessonPerformancePanel` | Bearer token | Returns analytics scoped to one saved lesson. |
| `GET /api/v1/quiz/health` | `QuizServiceStatusChip` | No auth required | Returns quiz service health and orchestrator status. |

---

## 3.15 Lessons endpoints (`/api/v1/lessons`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/lessons/generate` | `LessonBuilderWizard` | Bearer token, `multipart/form-data` with required `prompt` and optional controls/files | Returns multi-page lesson payload (`pages`, `navigation`, quality metrics). |
| `POST /api/v1/lessons/save` | `SaveLessonButton` | Bearer token, JSON `LessonSaveRequest` containing generated lesson content and progress fields | Persists lesson. Returns `SavedLessonDetail`. |
| `GET /api/v1/lessons` | `SavedLessonsPage` | Bearer token, query: `limit`, `offset` | Returns list of `SavedLessonSummary` (with progress snapshot). |
| `GET /api/v1/lessons/{lesson_id:uuid}` | `LessonViewerPage` | Bearer token | Returns full saved lesson and updates `last_opened_at`. |
| `PATCH /api/v1/lessons/{lesson_id:uuid}/progress` | `LessonProgressTracker` | Bearer token, JSON: `{ current_page_id?, completed_page_ids? }` | Updates resume state. If `current_page_id` is explicit `null`, backend resets to default page. |
| `GET /api/v1/lessons/health` | `LessonServiceStatusChip` | No auth required | Returns lessons API health metadata. |

Important implementation details for `POST /lessons/generate`:
- Use `FormData`, not JSON.
- Required field: `prompt` (minimum 10 chars).
- Optional fields include: `topic`, `subject`, `subtopics`, `learning_objectives`, `current_level`, `learning_style`, `learning_pace`, `daily_study_time_minutes`, `max_quiz_questions`, `quiz_question_types`, `include_mindmap`, `include_coding_exercises`, `include_answer_key`, and uploaded `files`.

`FormData` example:

```ts
const fd = new FormData();
fd.append("prompt", prompt);
fd.append("topic", topic);
fd.append("include_mindmap", String(includeMindmap));
for (const file of files) fd.append("files", file);
```

---

## 3.16 Coding problem endpoints (mounted directly under `/api/v1`)

| Endpoint | Frontend component / feature | Request from frontend | Response usage / implementation details |
|---|---|---|---|
| `POST /api/v1/lessons/{lesson_id:uuid}/coding-problems/generate` | `LessonCodingGeneratorPanel` | Bearer token, JSON: `{ decision_mode, max_problems }` | Generates coding problems linked to saved lesson. `decision_mode`: `auto`, `force`, `skip`. |
| `GET /api/v1/lessons/{lesson_id:uuid}/coding-problems` | `LessonCodingList` | Bearer token | Returns coding problem summaries for lesson. |
| `GET /api/v1/coding-problems/{problem_id:uuid}` | `CodingProblemDetailPage` | Bearer token, optional query `include_solution`, `include_hidden_tests` | Returns full problem detail; keep both query flags `false` for learner mode. |
| `POST /api/v1/coding-problems/{problem_id:uuid}/run` | `CodingSandboxRunButton` | Bearer token, JSON: `{ source_code, language_id?, stdin? }` | Runs code quickly; stores an attempt of mode `run`. Requires `developer`/`enterprise`. |
| `POST /api/v1/coding-problems/{problem_id:uuid}/submit` | `CodingSubmitButton` | Bearer token, JSON: `{ source_code, language_id? }` | Evaluates against all test cases and stores `submit` attempt. Requires `developer`/`enterprise`. |
| `GET /api/v1/coding-problems/{problem_id:uuid}/attempts` | `CodingAttemptsDrawer` | Bearer token, query: `limit`, `offset` | Returns attempt history for the coding problem. |

---

## 4. Recommended frontend feature map

Suggested feature-to-endpoint ownership (proposed):

- `features/auth`: all `/auth` endpoints
- `features/account`: `/users/profile`, `/users/subscription`
- `features/notifications`: `/notifications/subscribe`
- `features/notes`: `/notes/*` and `/documents/upload`
- `features/knowledge`: `/knowledge/*` and `/notes/graph-visualizer`
- `features/recommendations`: `/recommendations/*`
- `features/flashcards`: `/learning/*`
- `features/gamification`: `/gamification/*`
- `features/quiz`: `/quiz/*`
- `features/lessons`: `/lessons/*`
- `features/coding`: `/judge/*`, editor websocket, and coding problem endpoints
- `features/system`: root `/health` and service health endpoints

## 5. Common frontend pitfalls to avoid

- Do not send JSON for upload/generation endpoints that expect `multipart/form-data`.
- Do not forget to include Bearer token for protected endpoints.
- Handle `202 Accepted` as asynchronous processing (not immediate completion).
- Guard sandbox features (`/judge/*`, coding run/submit) behind subscription checks in UI to avoid avoidable `403` responses.
- Keep retry analytics stable by reusing the same `quiz_id` when evaluating re-attempts of the same quiz.

## 6. Quick checklist for implementation

- Build shared API client with auth + error handling.
- Add SSE helper for recommendation stream.
- Add websocket manager for editor execution.
- Add upload utilities (`FormData`) for notes/documents/lessons.
- Implement feature slices based on section 4 map.
- Add typed DTOs that mirror backend schemas.
- Add optimistic UI updates for delete/update flows.
