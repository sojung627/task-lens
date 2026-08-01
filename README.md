# TaskLens

## 프로젝트를 세 줄로 설명하면

- 무슨 주제인가: 음성, 문서, 장문의 업무 지시를 AI가 이해하고 실행 가능한 업무 단위로 정리하는 자동화 서비스입니다.
- 무엇이 문제였나: 긴 설명에서 목표, 순서, 담당자, 기한, 확인 사항을 사람이 매번 다시 분리해야 했습니다.
- 그래서 무엇을 만들었나: 입력 내용을 분석해 체크리스트를 만들고, 진행 상태와 메모, 파일, 알림까지 한 작업 공간에서 관리하는 웹 서비스를 만들었습니다.

## 프로젝트 소개

TaskLens는 음성이나 장문의 업무 지시를 이해하기 쉬운 체크리스트로 자동 변환하는 AI 업무 정리 도구입니다.

사용자가 음성, 텍스트, PDF, DOCX, 소스 코드 파일 등을 입력하면 AI가 다음 정보를 구분합니다.

- 전체 요약
- 핵심 목표
- 핵심 논점과 확정된 결정
- 실제 수행할 작업
- 작업 순서와 선행 관계
- 우선순위
- 기한
- 담당자와 제출 대상
- 완료 조건
- 확인이 필요한 내용
- 애매하거나 누락된 지시
- 어려운 용어와 쉬운 설명

분석 결과는 일회성 답변으로 끝나지 않습니다. MySQL에 대화, 파일, 분석, 체크리스트, 메모, 알림을 저장하고 사용자가 작업 상태를 직접 변경할 수 있습니다.

## 해결하려는 문제

업무 지시를 들을 때 다음 과정은 반복적으로 발생합니다.

1. 긴 설명을 다시 읽거나 듣습니다.
2. 실제 해야 할 일을 찾습니다.
3. 먼저 해야 할 일과 나중에 할 일을 나눕니다.
4. 담당자, 기한, 제출 기준을 따로 기록합니다.
5. 모르는 용어를 다시 검색합니다.
6. 진행 상황을 별도 메모나 체크리스트에 옮깁니다.

TaskLens는 이 과정을 입력, 분석, 저장, 실행 관리의 한 흐름으로 자동화합니다.

## 구현 기능

### AI 업무 분석

- 일반 대화와 업무 지시를 구분합니다.
- 업무가 있을 때만 구조화된 분석 결과를 생성합니다.
- 회의 내용은 요약, 핵심 논점, 결정 사항으로 별도 정리합니다.
- 원문에 없는 기한, 담당자, 결정 사항을 만들지 않도록 시스템 규칙을 적용했습니다.
- AI 응답을 Pydantic 스키마로 검증합니다.
- JSON 형식이나 필수 항목이 잘못되면 오류 이유를 포함해 한 번만 교정 요청합니다.
- 인증 오류, 요청 제한, 시간 초과, 외부 서비스 장애를 서로 다른 사용자 문구로 처리합니다.

### 음성 입력

- 브라우저에서 마이크 녹음을 시작하고 종료할 수 있습니다.
- 녹음된 WEBM 음성을 서버에서 텍스트로 변환합니다.
- MP3, MP4, MPEG, MPGA, M4A, OGG, WAV, WEBM, FLAC 파일 업로드를 지원합니다.
- 음성 파일을 채팅에 첨부하면 자동으로 텍스트를 추출한 뒤 AI 분석 문맥에 포함합니다.

### 문서와 코드 파일 분석

- TXT, MD, CSV, JSON, XML, YAML, LOG
- PDF, DOCX
- PY, JS, JSX, TS, TSX, HTML, CSS, SQL, JAVA, C, CPP, H
- 파일명, 확장자, 크기, MIME 형식을 검증합니다.
- 경로 조작을 막기 위해 원본 경로를 제거하고 안전한 저장 이름을 생성합니다.
- 파일 크기와 추출 텍스트 길이에 제한을 둡니다.

### 대화 작업 공간

- 대화와 메시지를 데이터베이스에 저장합니다.
- 첫 입력을 기반으로 대화 제목을 생성합니다.
- 대화 제목 변경, 휴지통 이동, 복원, 영구 삭제를 지원합니다.
- 대화 검색과 최근 파일 목록을 제공합니다.
- 첨부 파일과 AI 생성 파일을 다시 내려받을 수 있습니다.
- API 응답 배열이 비어 있거나 일부 필드가 누락돼도 화면이 중단되지 않도록 정규화합니다.

### 체크리스트 실행 관리

- 작업 상태를 대기, 진행 중, 완료로 변경합니다.
- 완료된 작업 수를 기준으로 진행률을 계산합니다.
- 작업 제목, 설명, 우선순위, 기한, 담당자, 제출 대상, 완료 조건을 수정합니다.
- 작업을 삭제하고 남은 작업 순서를 자동으로 다시 정리합니다.
- 체크리스트가 비어 버리지 않도록 마지막 작업 삭제를 차단합니다.
- 같은 대화에서 AI 분석이 다시 실행돼도 기존 작업 상태를 보존합니다.

### 메모와 알림

- 대화별 메모를 저장합니다.
- 특정 작업 또는 대화 전체에 알림을 등록합니다.
- 모든 알림 시간은 서버에서 UTC로 저장합니다.
- 프론트엔드는 만료된 알림을 주기적으로 확인합니다.
- 브라우저 알림 권한이 허용된 경우 운영체제 알림을 표시합니다.
- 확인한 알림은 다시 노출되지 않도록 상태를 변경합니다.

### 데이터베이스

애플리케이션 시작 시 MySQL 데이터베이스와 필요한 테이블을 확인합니다.

- conversations
- messages
- files
- analyses
- tasks
- reminders

테이블이 없으면 SQLAlchemy 메타데이터를 기준으로 생성합니다. 기존 conversations 테이블에 상태, 메모, 삭제 시간 열이 없으면 호환 열을 추가합니다.

테스트 환경에서는 SQLite를 사용할 수 있습니다. 운영 환경은 MySQL을 기준으로 구성했습니다.

## 기술 스택

### Backend

- Python 3.14
- FastAPI
- Pydantic과 Pydantic Settings
- SQLAlchemy Core
- MySQL과 PyMySQL
- HTTPX
- PyPDF
- python-docx
- Pytest

### Frontend

- TypeScript
- React 19
- Vite
- Tailwind CSS 4
- Axios
- Font Awesome Free

### AI

- Groq Chat Completions API
- Qwen 계열 대화 모델
- Groq Speech-to-Text API
- Whisper Large V3 Turbo

### Deployment

- Docker Compose
- MySQL 8.4
- Nginx
- 비루트 Python 애플리케이션 사용자
- 영구 MySQL 볼륨과 파일 저장 볼륨

## 전체 처리 흐름

```text
텍스트, 음성, 문서 입력
→ 파일 형식과 크기 검증
→ 문서 텍스트 추출 또는 음성 인식
→ 기존 대화 문맥 결합
→ AI 구조화 JSON 생성
→ Pydantic 검증
→ 잘못된 형식이면 오류 이유를 포함해 1회 교정
→ 대화, 파일, 분석, 작업을 MySQL에 저장
→ React 작업 공간에 결과 표시
→ 사용자가 상태, 메모, 알림을 계속 관리
```

## 프로젝트 구조

```text
TaskLens
├── backend
│   ├── app
│   │   ├── core
│   │   ├── db
│   │   ├── repositories
│   │   ├── routers
│   │   ├── schemas
│   │   └── services
│   ├── tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── components
│   │   ├── config
│   │   ├── hooks
│   │   ├── pages
│   │   └── types
│   ├── Dockerfile
│   └── nginx.conf
├── docs
│   ├── AI_USAGE_LOG.md
│   ├── DEMO_SCRIPT.md
│   ├── OPERATIONS.md
│   └── RETROSPECTIVE.md
├── docker-compose.yml
├── .env.example
├── .env.docker.example
└── README.md
```

## 로컬 실행

### 1. MySQL 준비

MySQL 서버를 실행한 뒤 프로젝트 루트의 예시 환경 파일을 복사합니다.

Windows PowerShell

```powershell
Copy-Item .env.example .env
```

macOS 또는 Linux

```bash
cp .env.example .env
```

.env에서 다음 값을 실제 환경에 맞게 설정합니다.

```text
GROQ_API_KEY=발급받은_API_키
DATABASE_URL=mysql+pymysql://tasklens:비밀번호@127.0.0.1:3306/tasklens?charset=utf8mb4
ALLOW_DEGRADED_STARTUP=false
```

### 2. 백엔드 실행

프로젝트 루트에서 실행합니다.

```bash
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

백엔드가 시작되면 데이터베이스와 테이블을 자동으로 확인합니다.

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

개발 서버는 API 요청을 127.0.0.1:8000으로 프록시합니다. 브라우저에서 다음 주소로 접속합니다.

```text
http://localhost:5173
```

## Docker Compose 실행

### 1. 환경 파일 준비

```bash
cp .env.docker.example .env
```

Windows에서는 파일 탐색기 또는 PowerShell의 Copy-Item 명령을 사용하면 됩니다.

다음 값을 반드시 변경합니다.

```text
GROQ_API_KEY
MYSQL_ROOT_PASSWORD
MYSQL_PASSWORD
```

### 2. 서비스 시작

```bash
docker compose up --build -d
```

접속 주소

```text
http://localhost:8080
```

상태 확인

```bash
docker compose ps
docker compose logs -f backend
```

종료

```bash
docker compose down
```

데이터까지 삭제할 때만 다음 명령을 사용합니다.

```bash
docker compose down -v
```

## 주요 API

```text
GET     /health
GET     /api/workspace
POST    /api/chat
POST    /api/audio/transcribe
PATCH   /api/conversations/{conversation_id}
DELETE  /api/conversations/{conversation_id}
POST    /api/conversations/{conversation_id}/restore
DELETE  /api/conversations/{conversation_id}/permanent
PUT     /api/conversations/{conversation_id}/notes
PATCH   /api/conversations/{conversation_id}/tasks/{task_id}
DELETE  /api/conversations/{conversation_id}/tasks/{task_id}
POST    /api/conversations/{conversation_id}/reminders
GET     /api/reminders/due
PATCH   /api/reminders/{reminder_id}
GET     /api/files/{file_id}/download
POST    /api/tasks/analyze
```

FastAPI 자동 문서

```text
http://127.0.0.1:8000/docs
```

## 검증 방법

백엔드 테스트

```bash
DATABASE_URL=sqlite+pysqlite:///./tasklens_test.db ALLOW_DEGRADED_STARTUP=false GROQ_API_KEY= python -m pytest -q
```

프론트엔드 타입 검사와 빌드

```bash
cd frontend
npm run build
```

프론트엔드 정적 검사

```bash
cd frontend
npm run lint
```

## 오류 처리 원칙

프론트엔드에는 백엔드 로그를 확인하라는 개발자용 문구를 표시하지 않습니다.

- 사용자가 다시 시도할 수 있는 행동을 설명합니다.
- API 키 누락, 인증 실패, 요청 제한, 시간 초과, 외부 장애를 구분합니다.
- 잘못된 파일, 크기 초과, 읽을 수 없는 문서를 구체적으로 안내합니다.
- 데이터가 비정상 형태로 반환돼도 빈 배열과 기본값으로 복구합니다.
- 중요한 기한과 담당자는 원문과 다시 확인하도록 안내합니다.

## 운영 전 확인 사항

현재 구현은 과제 제출과 단일 조직 내부 사용을 위한 상용화 가능한 기준선입니다. 불특정 다수에게 공개하는 SaaS로 운영할 때는 다음 항목을 추가해야 합니다.

- 사용자 계정과 조직별 권한 분리
- 파일 다운로드 접근 권한 검증
- HTTPS 인증서와 도메인
- API 요청 제한과 감사 로그
- 데이터 보존 기간과 개인정보 삭제 정책
- MySQL 정기 백업과 복구 훈련
- 실제 트래픽을 기준으로 한 부하 테스트
- 외부 AI 전송 데이터에 대한 조직 보안 검토

운영 절차는 docs/OPERATIONS.md에 정리했습니다.

## 과제 제출 자료

- AI 활용 기록: docs/AI_USAGE_LOG.md와 TaskLens_AI_활용_기록.docx
- 회고: docs/RETROSPECTIVE.md와 TaskLens_회고.docx
- 실행 녹화 대본: docs/DEMO_SCRIPT.md
- 코드: 이 저장소 전체
