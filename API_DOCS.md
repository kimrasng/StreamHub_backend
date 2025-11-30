# StreamHub Backend API Documentation

이 문서는 `StreamHub`의 REST API 및 WebSocket 엔드포인트를 정리합니다.

**요약**
- 인증: Token 기반(DRF `TokenAuthentication`) — `Login`에서 발급된 토큰을 `Authorization: Token <token>` 헤더로 전송하거나, 프론트엔드에서 이미 사용하는 방식에 따라 `Bearer` 형태를 사용합니다 (백엔드 `UserListView`에서 Cloudflare 호출 시 `Bearer` 사용).
- 응답 형식: JSON

**Models (간단 요약)**
- `User` (Django 기본)
- `Profile` : `user` (OneToOne), `nickname` (CharField)
- `Stream` : `user` (OneToOne), `stream_key`, `stream_url`, `viewer_url` (Cloudflare uid)
- `ChatMessage` : `user`, `stream`, `message`, `timestamp`
- `Ban` : `streamer`, `banned_user`, unique(streamer, banned_user)

**Endpoints**

- **`POST /api/signup/`** : 회원가입
  - **Auth:** 없음
  - **Request JSON:**
    - `username` (string, required)
    - `password` (string, required)
    - `profile` (object, optional)
      - `nickname` (string, optional)
  - **Response (201):** 생성된 `User` (id, username, profile.nickname)
  - **Notes:** 사용자 생성 시 Cloudflare Stream 생성 시도. 실패 시 개발용 placeholder stream 생성.

- **`POST /api/login/`** : 로그인
  - **Auth:** 없음
  - **Request JSON:**
    - `username` (string)
    - `password` (string)
  - **Response (200):**
    - `token` (string)
    - `username` (string)
    - `nickname` (string)
  - **Error (400):** `{'error': 'Invalid Credentials'}`

- **`POST /api/logout/`** : 로그아웃
  - **Auth:** Token required
  - **Request:** 빈 바디
  - **Response (204):** No Content

- **`GET /api/stream/<username>/`** : 특정 스트리머의 스트림 정보 조회
  - **Auth:** 공개
  - **Response (200):**
    - `username`, `nickname`, `stream_key`, `stream_url`, `stream_uid`
  - **Errors:** 404 if user/stream not found

- **`GET /api/users/`** : 사용자 목록 (라이브 상태 포함)
  - **Auth:** 공개
  - **Response (200):** Array of objects:
    - `username`, `nickname`, `is_live` (bool), `thumbnail` (nullable)
  - **Notes:** Cloudflare Stream API를 호출해 `viewer_url` UID를 기준으로 라이브/썸네일 정보를 매칭.

- **`GET /api/profile/`** : 내 프로필 조회
  - **Auth:** Token required
  - **Response:** `ProfileSerializer` ({`nickname`, `username`})

- **`PUT /api/profile/`** : 내 프로필 수정
  - **Auth:** Token required
  - **Request JSON:** profile 필드들(예: `nickname`)
  - **Response:** 업데이트된 프로필 JSON

- **`POST /api/password/change/`** : 비밀번호 변경
  - **Auth:** Token required
  - **Request JSON:**
    - `old_password` (string, required)
    - `new_password` (string, required)
  - **Response (200):** `{'status': 'password set'}`
  - **Errors:** 400 with serializer errors or wrong old password

- **`GET /api/stream/<username>/banned/`** : 스트리머의 차단된 사용자 목록
  - **Auth:** 스트리머 자신만 접근 (custom permission `IsStreamer`)
  - **Response (200):** Array of `{ 'banned_username': <username> }`

- **`POST /api/ban/`** : 사용자 차단
  - **Auth:** Token required
  - **Request JSON:** `{ 'banned_user': '<username>' }`
  - **Response (201):** `{'status': '<username> has been banned.'}`
  - **Errors:** 404 if target user not found, 400 if banning self.

- **`POST /api/unban/`** : 사용자 차단 해제
  - **Auth:** Token required
  - **Request JSON:** `{ 'banned_user': '<username>' }`
  - **Response (200):** `{'status': '<username> has been unbanned.'}`
  - **Errors:** 404 if user/ban not found

**WebSocket**

- **`ws/chat/<room_name>/`** (from `backend/api/routing.py`)
  - **Purpose:** 스트리머(룸 이름) 채팅
  - **Auth:** 소비자에서 `self.scope.get('user')` 사용 — Django Channels의 인증 미들웨어 (예: `AuthMiddlewareStack`)이 설정되어 있어야 합니다. 로그인이 안되어 있으면 메세지 전송 거부.
  - **Behavior:**
    - 접속 시 최근 채팅(최대 50건) 전송
    - 수신 메시지 포맷: `{ "message": "..." }`
    - 브로드캐스트 포맷: `{ "message": "...", "username": "...", "display_name": "..." }`
    - 차단된 사용자(Ban)여부 체크 후 차단 시 오류 반환
  - **Notes:** `ChatConsumer`는 `self.scope['user']`에 의존하므로 Channels의 토큰 인증(예: `TokenAuthMiddleware`)이나 세션 인증이 WebSocket 스코프에 적용되어야 합니다.

**시리얼라이저 요약** (`backend/api/serializers.py`)
- `ProfileSerializer`: `nickname`, `username` (read_only via user)
- `UserPasswordSerializer`: `old_password`, `new_password`
- `UserSerializer`: `id`, `username`, `password` (write_only), `profile` (nested `ProfileSerializer`)
  - create()에서 사용자 생성 후 Cloudflare Stream 생성 시도

**실행/테스트 가이드**

- 로컬 개발 환경에서 Cloudflare 관련 설정이 없을 경우 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` 미설정으로 예외가 발생할 수 있습니다. 현재 구현은 예외 발생 시 로컬 placeholder `Stream`을 생성합니다.

- 토큰 생성 및 사용 예시 (curl):

```bash
# 로그인
curl -X POST http://localhost:8000/api/login/ -H "Content-Type: application/json" -d '{"username":"alice","password":"pw"}'

# 받은 토큰을 Authorization 헤더에 포함
curl -X GET http://localhost:8000/api/profile/ -H "Authorization: Token <token>"
```

- WebSocket (wscat 예시, 토큰 인증 미들 경우):
```bash
# 만약 querystring으로 토큰을 전달하는 custom middleware가 있다면
wscat -c "ws://localhost:8000/ws/chat/alice/?token=<token>"
```

**파일 위치**
- 엔드포인트 정의: `backend/api/urls.py`
- 뷰 구현: `backend/api/views.py`
- 시리얼라이저: `backend/api/serializers.py`
- 모델: `backend/api/models.py`
- WebSocket routing: `backend/api/routing.py`
- WebSocket consumer: `backend/api/consumers.py`

---