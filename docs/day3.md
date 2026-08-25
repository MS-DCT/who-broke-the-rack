# 📅 Day 3 — 2026-08-25

Day 3 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 3 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | 작성 예정 |
| **B** | Automation / Troubleshooting | Rule 기반 diagnosis Engine 구현 |
| **C** | Platform / Visualization | 작성 예정 |

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

> 작성 예정
