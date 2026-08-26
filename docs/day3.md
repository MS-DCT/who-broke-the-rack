# 📅 Day 3 — 2026-08-25

Day 3 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 3 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | 작성 예정 |
| **B** | Automation / Troubleshooting | Rule 기반 diagnosis Engine 구현 |
| **C** | Platform / Visualization | FastAPI Incident Controller, Diagnosis 연동, Evidence/Diagnosis DB 저장, Incident Timeline 및 React Live Diagnosis UI 구현 |
---

# 👤 A — Day 3

> 작성 예정

---

## 👤 B — Day 3

> Day 2에서 수집한 Network / OS / Service Evidence를 기준으로 장애 원인을 판별하는 Rule 기반 Diagnosis Engine 구현

> C의 FastAPI Incident Controller에서 직접 호출할 수 있는 Incident Runner를 추가하고, 최신 Evidence와 Diagnosis 결과를 JSON 형태로 반환하도록 구성

### Development / Architecture

- Diagnosis 코드는 B 담당 영역인 `automation/diagnosis/`에 구성
- 기존 `backend/**`, `frontend/**`, Day 1/2 코드 수정 없음
- B는 최신 Evidence 수집 및 Root Cause 판별 담당
- Incident History와 Timeline 영구 저장은 C가 담당

```text
C Incident Controller
→ incident_id / host 전달
→ B Evidence 수집
→ Diagnosis Rule 판별
→ Evidence + Diagnosis 반환
→ C DB / Timeline 저장
```

생성 파일:

```text
automation/ansible/playbooks/incident_diagnostic.yml
automation/diagnosis/__init__.py
automation/diagnosis/diagnosis_engine.py
automation/diagnosis/incident_runner.py
automation/diagnosis/tests/test_diagnosis_engine.py
automation/diagnosis/tests/test_incident_runner.py
```

### Implementation

#### Diagnosis Decision Tree

Rule 평가 순서:

```text
Hardware → POST/Boot → Network → Service
```

Evidence가 부족하거나 `UNKNOWN`, `SKIP` 상태이면 장애로 추측하지 않고 `INSUFFICIENT_EVIDENCE`로 처리

#### `HW-STORAGE-01`

- 현재 Storage 상태가 `WARN` 또는 `FAIL`인지 확인
- 현재 Incident 이후 발생한 Storage IML Event 확인
- 현재 Storage 상태가 정상인 경우 과거 IML Message만으로 장애 판정하지 않음
- Hardware 장애는 자동 복구하지 않고 Escalation 대상으로 반환

#### `BOOT-OS-01`

- POST 상태가 명시적으로 정상인지 확인
- 이후 Boot 또는 OS 접근 상태가 `FAIL`이면 Boot/OS 장애로 판정
- Boot Evidence가 없거나 `UNKNOWN`이면 장애로 추측하지 않음
- Redfish의 `FinishedPost` 값을 `PASS`로 정규화

#### `NET-ROUTE-01`

- `nic_link`, `ip_address`가 모두 `PASS`인지 선행 확인
- 이후 `gateway` 또는 `routes`가 `FAIL`이면 Routing 장애로 판정
- NIC/IP가 정상 확인되지 않으면 Routing 문제로 단정하지 않음
- `pxe_reachability` 실패는 Route 장애 조건에서 제외
- 판정에 사용한 NIC, IP, Gateway, Routes를 `matched_evidence`에 포함

#### `SVC-HTTP-01`

- NIC, IP, Gateway, Routes가 모두 `PASS`인지 선행 확인
- 이후 Process, Listening Port, HTTP Health 중 하나가 `FAIL`이면 Service 장애로 판정
- Network와 Service가 함께 실패하면 Network Rule 우선
- `SKIP`, `UNKNOWN`, 누락은 `FAIL`로 처리하지 않음

Rule 결과:

```text
rule_id
root_cause
matched_evidence
recommended_action
severity
```

Rule 미매칭 시:

- Evidence가 충분하면 `NO_ISSUE`
- Evidence가 부족하면 `INSUFFICIENT_EVIDENCE`
- `rule_id`는 `null`
- 부족한 항목은 `evidence_gaps`에 기록
  - `MISSING`
  - `NOT_CONFIRMED_PASS`

### Incident Runner

C 호출용 Python 함수:

```python
from automation.diagnosis.incident_runner import run_incident

result = run_incident(
    incident_id,
    host,
    incident_started_at=incident_started_at,
    hardware_evidence=hardware_evidence,
)
```

- `incident_id`, `host`
  - 필수 입력
- `incident_started_at`
  - 현재 Incident와 과거 IML Event 구분
- `hardware_evidence`
  - A의 Hardware / POST Evidence 병합
- 임시 디렉터리에서 Evidence 수집 후 자동 정리
- B 영역에 Incident History를 별도로 저장하지 않음
- 함수 호출 실패 시 `IncidentRunnerError` 반환
- 독립 실행을 위한 CLI 유지

### Evidence 반환 형식

C에서 DB에 바로 저장할 수 있도록 check 단위 flat 구조로 반환

```json
{
  "incident_id": "INC-20260825-001",
  "timestamp": "2026-08-25T00:01:00Z",
  "host": "dca-target01",
  "layer": "network",
  "check_name": "gateway",
  "result": "FAIL",
  "value": null,
  "detail": "Gateway route check failed",
  "source": "ansible",
  "severity": null
}
```

필드 규칙:

- `layer`
  - `hardware`, `boot`, `network`, `os`, `service`
- `check_name`
  - snake_case
- `result`
  - `PASS`, `WARN`, `FAIL`, `UNKNOWN`, `SKIP`
- `detail`
  - 단수 필드명 사용
- `schema_version`
  - 사용하지 않음

입력 호환을 위해 `detail`, legacy `details`를 모두 읽을 수 있지만 최종 출력은 `detail`만 사용

### Test / Verification

- Diagnosis / Incident Runner Unit Test 24개 통과
- Python 문법 검사 통과
- `incident_diagnostic.yml` syntax-check 통과
- Network 선행 조건 검증
- Network / Service 장애 우선순위 검증
- 과거 IML Event 오매칭 방지 검증
- Hardware / Boot Evidence 부족 처리 검증
- Flat Evidence 및 JSON 직렬화 검증
- 실제 Ansible 실행은 mock 처리
- 실서버 접속 및 복구 명령은 실행하지 않음

최신 Diagnosis JSON 생성:

```text
evidence/day3/diagnosis/dca-target01.diagnosis.json
evidence/day3/diagnosis/dca-target02.diagnosis.json
evidence/day3/diagnosis/dca-spare01.diagnosis.json
```

현재 결과:

- `dca-target01`
  - `INSUFFICIENT_EVIDENCE`
- `dca-target02`
  - `INSUFFICIENT_EVIDENCE`
- `dca-spare01`
  - `INSUFFICIENT_EVIDENCE`

공통 부족 항목:

- Hardware System Health
- Power State
- Storage Health
- POST 상태
- Boot 또는 OS 접근 상태
- HTTP Health가 `SKIP` 상태

정식 Hardware / Boot Evidence가 아직 병합되지 않았으므로 수동 PASS 값을 임의로 삽입하지 않음

### Day 3 Outcome

- Rule 기반 Diagnosis Engine 구현
- `HW-STORAGE-01` 구현
- `BOOT-OS-01` 구현
- `NET-ROUTE-01` 구현
- `SVC-HTTP-01` 구현
- Evidence 부족 및 Rule 우선순위 처리
- C 호출용 `run_incident()` 함수 및 CLI 구현
- Flat Evidence / Diagnosis 반환 형식 확정
- Day 3 Diagnosis JSON 3개 최신화
- B 코드 GitHub 반영 완료

남은 통합 작업:

```text
C Incident 생성
→ B run_incident() 호출
→ 최신 Evidence 수집
→ Diagnosis 반환
→ C DB 저장
→ Timeline / Root Cause UI 표시
```

---

# 👤 C — Day 3

> FastAPI 기반 Incident Controller를 구현하고 B의 `run_incident()` Diagnosis Engine과 실제 연동

> B에서 반환한 Evidence / Diagnosis 결과를 DB에 저장하고 Incident 단위 Timeline API 및 React Live Diagnosis UI까지 구현

## Development / Architecture

C는 Platform / Visualization 영역을 담당하며 Day 3에서 아래 전체 흐름을 구현하였다.

```text
React Dashboard
→ FastAPI Incident Controller
→ Incident ID 생성
→ B run_incident() 호출
→ Ansible Evidence 수집
→ Diagnosis Engine 실행
→ Evidence / Diagnosis 반환
→ SQLite DB 저장
→ Incident Timeline 생성
→ Root Cause / Timeline UI 표시
```

생성 및 수정 파일:

```text
backend/incident_controller.py
backend/diagnosis_service.py
backend/incident_workflow.py
backend/timeline.py
backend/models.py
backend/main.py

frontend/src/IncidentPanel.jsx
frontend/src/App.jsx
frontend/src/App.css
```

## Incident Controller

새로운 Incident 생성 API를 구현하였다.

```text
POST /incidents/start/{server_id}
```

지원 Server / Host Mapping:

```text
server-205 → dca-target01
server-206 → dca-mgmt01
server-207 → dca-target02
server-208 → dca-spare01
```

Incident 생성 시 시간 정보와 UUID suffix를 조합하여 고유 Incident ID를 자동 생성한다.

예시:

```text
INC-20260825-143129-E0DA
```

생성된 Incident는 DB에 저장되며 초기 상태는 다음과 같다.

```text
status = DETECTED
```

Swagger를 통해 Incident 생성 및 DB 저장을 실제 검증하였다.

## Diagnosis Engine Integration

B가 제공한 Python Interface를 FastAPI Incident Workflow에서 직접 호출하도록 연동하였다.

```python
from automation.diagnosis.incident_runner import run_incident

result = run_incident(
    incident_id=incident_id,
    host=host,
    incident_started_at=incident_started_at
)
```

C의 `incident_workflow.py`에서는 다음 순서로 동작한다.

```text
Incident 조회
→ server_id 기반 Target Host 결정
→ B run_incident() 실행
→ Ansible Evidence 수집
→ Diagnosis Engine 실행
→ Evidence / Diagnosis 결과 반환
→ C DB 저장
```

Diagnosis 실행 API:

```text
POST /incidents/{incident_id}/diagnose
```

실제 `dca-target02` 서버를 대상으로 실행하여 다음 연결을 검증하였다.

```text
FastAPI
→ B Incident Runner
→ Ansible
→ Target Server
→ Diagnosis Engine
```

## SSH / Ansible Integration

Management Server인 `dca-mgmt01`에서 Target Server인 `dca-target02`로 자동 진단을 실행할 수 있도록 SSH Key 인증을 구성하였다.

```text
dca-mgmt01 (.206)
→ SSH Key Authentication
→ dca-target02 (.207)
```

비대화형 SSH 접속 확인:

```text
ssh BatchMode Test
→ dca-target02
```

Ansible 연결 확인:

```text
dca-target02 | SUCCESS
ping: pong
```

이를 통해 FastAPI 내부에서 별도의 비밀번호 입력 없이 Ansible Diagnostic Playbook을 실행할 수 있도록 구성하였다.

## Evidence Persistence

B의 `run_incident()`가 반환하는 Flat Evidence를 SQLite DB에 저장하도록 `diagnosis_service.py`를 구현하였다.

사용되는 주요 Evidence 필드:

```text
incident_id
timestamp
host
layer
check_name
result
severity
value
detail
source
```

현재 C의 Evidence Model에 별도 Column이 없는 `value`, `detail`, `source`는 `details` 필드에 통합하여 저장하였다.

예시:

```text
Value: OK | Detail: Health=OK | Source: ansible
```

Evidence에 Severity가 없는 경우 Result 기준으로 보완한다.

```text
PASS    → INFO
WARN    → WARN
FAIL    → HIGH
UNKNOWN → WARN
SKIP    → INFO
```

동일 Incident에 Diagnosis가 이미 저장된 경우 기존 Timeline 중복 생성을 방지하기 위해 재실행을 차단하였다.

## Diagnosis Persistence

Day 3에서 Diagnosis 정보를 영구 저장하기 위한 `Diagnosis` DB Model을 추가하였다.

저장 필드:

```text
incident_id
rule_id
root_cause
matched_evidence
recommended_action
severity
diagnosis_status
evidence_gaps
timestamp
```

B가 반환한 Diagnosis 결과를 SQLite DB에 저장하고 `Incident.root_cause`에도 반영하였다.

실제 통합 테스트 결과:

```text
diagnosis_saved: true
evidence_count: 19
```

현재 Hardware / Boot Evidence 최종 병합 전 상태에서는 Diagnosis Engine이 장애 원인을 임의로 추측하지 않고 다음과 같이 반환하였다.

```text
diagnosis_status:
INSUFFICIENT_EVIDENCE

root_cause:
Insufficient evidence to determine a root cause
```

부족한 Hardware Evidence는 `evidence_gaps`를 통해 확인할 수 있도록 처리하였다.

## Incident Evidence Timeline

Incident 단위 전체 이벤트를 조회할 수 있는 API를 구현하였다.

```text
GET /incidents/{incident_id}/timeline
```

Timeline은 다음 이벤트를 하나의 Incident 기준으로 시간순 통합한다.

```text
INCIDENT
EVIDENCE
DIAGNOSIS
ACTION
```

실제 `dca-target02` 진단 결과:

```text
Incident Created     1
Evidence            19
Diagnosis            1
Total Timeline      21 Events
```

실제 API 테스트 결과:

```text
HTTP 200
event_count: 21
```

이를 통해 B가 생성한 Evidence와 Diagnosis가 C의 DB에 저장되고 하나의 Incident Timeline으로 연결되는 것을 확인하였다.

## React Live Incident Diagnosis UI

기존 Dashboard에 Day 3용 `Live Incident Diagnosis` 기능을 추가하였다.

추가 컴포넌트:

```text
frontend/src/IncidentPanel.jsx
```

사용자가 Target Server를 선택하고 다음 버튼을 누르면 전체 진단 Workflow가 자동 실행된다.

```text
Start Incident & Diagnose
```

실행 흐름:

```text
Incident 생성
→ B Diagnosis Engine 실행
→ Ansible Evidence 수집
→ Evidence DB 저장
→ Diagnosis DB 저장
→ Timeline 조회
→ React Dashboard 갱신
```

Dashboard 표시 정보:

```text
Incident ID
Target Host
Diagnosis Status
Evidence Count
Root Cause
Severity
Rule ID
Recommended Action
Incident Evidence Timeline
```

실제 `server-207 / dca-target02`를 대상으로 Frontend에서 전체 Workflow를 실행하였다.

최종 확인 결과:

```text
Target: dca-target02
Evidence: 19
Timeline: 21 events
Diagnosis 결과 표시 정상
Root Cause 표시 정상
```

이를 통해 다음 End-to-End 흐름을 실제 검증하였다.

```text
React
→ FastAPI
→ Incident Controller
→ B Diagnosis Engine
→ Ansible
→ Target Server
→ Evidence / Diagnosis
→ SQLite DB
→ Timeline API
→ React Dashboard
```

## Day 3 API

C가 Day 3에서 추가한 주요 API:

```text
POST /incidents/start/{server_id}

POST /incidents/{incident_id}/diagnose

GET /incidents/{incident_id}/timeline
```

기존 Day 2 기능을 유지하면서 Day 3 Incident Workflow를 확장하였다.

## Test / Verification

- Incident ID 자동 생성 확인
- Incident DB 저장 확인
- Diagnosis Table 생성 확인
- `dca-mgmt01 → dca-target02` SSH Key 인증 확인
- Ansible Ping `SUCCESS / pong` 확인
- FastAPI에서 B `run_incident()` 실제 호출 확인
- 실제 Target Server 대상 Ansible 진단 확인
- Ansible Evidence 19개 수집 확인
- Evidence DB 저장 확인
- Diagnosis DB 저장 확인
- `diagnosis_saved: true` 확인
- Root Cause DB 반영 확인
- Incident Timeline 21 Events 확인
- Timeline API HTTP 200 확인
- React Live Incident Diagnosis UI 동작 확인
- Frontend에서 Incident 생성 → Diagnosis → Timeline 전체 Workflow 확인
- Backend GitHub 반영 완료
- Frontend GitHub 반영 완료

## Day 3 Outcome

Day 3 C 구현 결과:

```text
Incident Controller                완료
Dynamic Incident ID                완료
B run_incident Integration         완료
Ansible Real Server Diagnosis      완료
Evidence Persistence               완료
Diagnosis Persistence              완료
Incident Root Cause                완료
Incident Evidence Timeline         완료
FastAPI Diagnosis API              완료
React Live Diagnosis Dashboard     완료
End-to-End Integration Test        완료
GitHub Push                        완료
```

C 담당 영역의 Day 3 기능 구현과 B Diagnosis Engine 연동은 완료하였다.

현재 남은 팀 최종 통합 작업:

```text
A Hardware / Boot Evidence 최종 생성
→ B hardware_evidence 병합
→ C Incident Workflow 최종 통합 확인
→ Hardware Evidence 포함 Diagnosis 재검증
```

C의 DB / Timeline / UI는 Hardware Evidence가 추가되어도 기존 구조를 그대로 사용할 수 있도록 구성하였다.
