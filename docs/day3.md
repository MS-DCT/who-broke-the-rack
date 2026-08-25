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

👤 B — Day 3

Day 2에서 수집한 Network / OS / Service Evidence를 기반으로 장애 원인을 판별하는 Rule 기반 Diagnosis Engine 구현

Development / Architecture

Diagnosis 코드는 B 담당 영역인 automation/diagnosis/에 구성

기존 backend/**, frontend/**, Day 1/2 코드 수정 없음

C의 FastAPI에서 직접 호출할 수 있도록 Python 함수와 CLI 제공

B는 최신 Evidence와 Diagnosis 결과만 반환

Incident History와 Timeline 영구 저장은 C가 담당

C Incident Controller
→ incident_id / host 전달
→ B Evidence 수집
→ Diagnosis Rule 판별
→ Evidence + Diagnosis 반환
→ C DB / Timeline 저장

Implementation

Diagnosis Rule

HW-STORAGE-01

현재 Storage 상태가 WARN 또는 FAIL인지 확인

현재 Incident 이후 발생한 Storage IML Event 확인

과거 IML Message만 존재하면 현재 장애로 판단하지 않음

Hardware 장애는 자동 복구하지 않고 Escalation 대상으로 반환

BOOT-OS-01

POST가 명시적으로 정상인지 확인

이후 Boot 또는 OS 접근 상태가 FAIL이면 Boot/OS 장애로 판단

Boot Evidence가 없거나 UNKNOWN이면 장애로 추측하지 않음

NET-ROUTE-01

nic_link, ip_address가 모두 PASS인지 선행 확인

이후 gateway 또는 routes가 FAIL이면 Routing 장애로 판단

NIC/IP가 정상 확인되지 않으면 Routing 문제로 단정하지 않음

pxe_reachability 실패는 Route 장애 조건에서 제외

SVC-HTTP-01

NIC, IP, Gateway, Routes가 모두 PASS인지 선행 확인

이후 Process, Listening Port, HTTP Health 중 하나가 FAIL이면 Service 장애로 판단

Network와 Service가 함께 실패하면 Network Rule 우선

Rule 평가 순서:

Hardware → POST/Boot → Network → Service

Rule이 매칭되면 다음 항목 반환:

rule_id
root_cause
matched_evidence
recommended_action
severity

Evidence가 부족하면 장애를 추측하지 않고 다음 상태로 반환:

diagnosis_status: INSUFFICIENT_EVIDENCE
rule_id: null
evidence_gaps: MISSING / NOT_CONFIRMED_PASS

Incident Runner

C 호출용 함수:

from automation.diagnosis.incident_runner import run_incident

result = run_incident(
    incident_id,
    host,
    incident_started_at=incident_started_at,
    hardware_evidence=hardware_evidence,
)

incident_id, host: 필수

incident_started_at: 현재 Incident와 과거 IML Event 구분

hardware_evidence: A의 Hardware / POST Evidence 병합

임시 디렉터리에서 Evidence 수집 후 자동 정리

B 영역에 Incident History를 별도로 누적하지 않음

함수 호출 실패 시 IncidentRunnerError 반환

독립 실행을 위한 CLI 유지

Evidence 반환 형식

C에서 DB에 바로 저장할 수 있도록 check 단위 flat 구조로 반환

{
  "layer": "network",
  "check_name": "gateway",
  "result": "FAIL",
  "value": null,
  "detail": "Gateway route check failed",
  "source": "ansible",
  "severity": null
}

필드 규칙:

layer

hardware, boot, network, os, service

check_name

snake_case

result

PASS, WARN, FAIL, UNKNOWN, SKIP

detail

단수 필드명 사용

schema_version

사용하지 않음

Test / Verification

Diagnosis / Incident Runner Unit Test 24개 통과

Python 문법 검사 통과

incident_diagnostic.yml syntax-check 통과

Network 선행 조건과 Service 우선순위 검증

과거 IML Event 오매칭 방지 검증

Evidence 부족 처리 검증

Flat Evidence 및 JSON 직렬화 검증

실제 서버 실행은 하지 않고 Ansible 호출은 mock 처리

최신 Diagnosis JSON 생성:

evidence/day3/diagnosis/dca-target01.diagnosis.json
evidence/day3/diagnosis/dca-target02.diagnosis.json
evidence/day3/diagnosis/dca-spare01.diagnosis.json

현재 결과:

dca-target01

INSUFFICIENT_EVIDENCE

dca-target02

INSUFFICIENT_EVIDENCE

dca-spare01

INSUFFICIENT_EVIDENCE

현재 Hardware / POST / Boot Evidence가 정식 파일로 병합되지 않았고 HTTP Health가 SKIP 상태이므로 정상적인 Evidence 부족 결과

수동 PASS 값은 임의로 삽입하지 않음

Day 3 Outcome

Rule 기반 Diagnosis Engine 구현

Hardware / Boot / Network / Service Rule 구현

Evidence 부족 및 Rule 우선순위 처리

C 호출용 run_incident() 함수와 CLI 구현

Flat Evidence / Diagnosis 반환 계약 확정

Day 3 Diagnosis JSON 3개 최신화

B 코드 GitHub 반영 완료

C DB / Timeline 실제 연동 및 실서버 End-to-End 검증 대기

---

# 👤 C — Day 3

> 작성 예정
