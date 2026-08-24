# WHO BROKE THE RACK?

> **Data Center Troubleshooting & Automated Recovery Platform**

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 1 — 2026-08-24** | 작성 예정 | 작성 예정 | FastAPI / SQLite / React Dashboard / GitHub 환경 구성 |

➡️ [Day 1 상세 작업 기록](docs/day1.md)

---

## 🅲 C — Day 1 Summary

### Development Environment
- `.206` Management Server 개발환경 구성
- Python / Git 환경 확인
- Node.js / npm 설치
- Node.js Library 오류 해결

### Backend
- FastAPI Backend 구성
- SQLite + SQLAlchemy 구성
- Incident / Evidence / Action Model 생성
- `/servers`, `/incidents`, `/evidence`, `/actions` API 구현
- CORS 구성
- Swagger 및 API 접근 확인

### Mock Data
- `MOCK-001` Incident 생성
- HARDWARE / POST_BOOT / NETWORK / OS Evidence 생성
- Mock Data 중복 생성 방지

### Frontend
- React + Vite 구성
- Rack Overview 구현
- 4대 Server Card 구현
- Evidence Timeline 구현
- PASS / FAIL / WARN / UNKNOWN 상태 UI 구성
- Dark Dashboard 구성
- FastAPI ↔ React 연동 확인

### Runtime
- FastAPI `8000/tcp` 접근 구성
- Vite `5173/tcp` 접근 구성
- Backend / Frontend 동시 실행 확인

### Git / GitHub
- Local Git Repository 구성
- `.gitignore` 구성
- 최초 Platform Commit 생성
- GitHub Organization Repository 연결
- Fine-grained PAT 인증 구성
- `main` Branch 최초 Push
- Secret / Private Key 검사
- Repository Public 전환

---

## 🏗 Current Flow

```text
SQLite
   ↓
FastAPI
   ↓
React
   ↓
Rack Overview + Evidence Timeline
```

---

## Repository

https://github.com/MS-DCT/who-broke-the-rack
