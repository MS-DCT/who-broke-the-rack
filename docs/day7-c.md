# 👤 C — Day 7

> Incident 전체 Lifecycle과 Physical Recovery 진행 상태를 Frontend에서 실시간 시각화하고, Rack Overview 및 CASE CLOSED 결과까지 하나의 운영 화면으로 연결

## 1. Day 7 C 목표

Day 6에서 구현한 Recovery Escalation UI를 확장하여 다음 항목을 구현했다.

```text
DETECTED
  ↓
INVESTIGATING
  ↓
ROOT_CAUSE_FOUND
  ↓
RECOVERING
  ↓
ESCALATING
  ↓
VERIFYING
  ↓
CLOSED
```

또한 Physical Recovery 진행 중 Rack Overview에서 장애 Target과 Spare 상태를 구분하도록 구성했다.

```text
Target #3   → FAILED
Spare #4    → SPARE / RECOVERING / READY
```

---

## 2. Incident State Machine UI

`frontend/src/IncidentPanel.jsx`에 Day 7 Incident State Machine을 추가했다.

상태 목록:

```text
DETECTED
INVESTIGATING
ROOT_CAUSE_FOUND
RECOVERING
ESCALATING
VERIFYING
CLOSED
```

현재 Incident / Diagnosis / Recovery / Escalation 상태를 조합하여 화면의 현재 Lifecycle 상태를 계산한다.

주요 매핑:

```text
Incident 생성                      → INVESTIGATING
Diagnosis MATCHED                  → ROOT_CAUSE_FOUND
Software Recovery 진행            → RECOVERING
Escalation 상태 존재               → ESCALATING
Escalation READY                   → VERIFYING
Incident status CLOSED             → CLOSED
```

각 단계는 `complete / active / pending` 상태로 표시되며 현재 단계가 시각적으로 강조된다.

---

## 3. Timeline 자동 Polling

기존 수동 Refresh Timeline 기능에 더해 현재 Incident가 존재하면 Timeline API를 2초 간격으로 자동 조회하도록 구성했다.

```text
GET /incidents/{incident_id}/timeline
        ↓
2초 Polling
        ↓
Incident Evidence Timeline 갱신
```

Day 6의 Escalation 2초 Polling과 함께 Recovery 진행 상태와 Timeline을 별도 새로고침 없이 확인할 수 있도록 구성했다.

---

## 4. Rack Overview Physical Recovery 상태 시각화

`App.jsx`에서 `IncidentPanel`의 현재 Platform 상태를 Parent로 전달하도록 `onPlatformStateChange` Callback을 추가했다.

Rack 상태 매핑:

```text
현재 Incident Target + Escalation 발생
    → FAILED

server-208 + SPARE_ACTIVATING / PXE / CONFIGURING
    → RECOVERING

server-208 + READY
    → READY

server-208 + Physical Recovery 미진행
    → SPARE
```

따라서 Physical Recovery 흐름 중 운영 화면에서 장애 서버와 대체 서버의 역할을 즉시 구분할 수 있다.

---

## 5. Day 7 Physical Recovery UI 전환 검증

검증 Incident:

```text
INC-20260902-181304-93AF
Target: server-207 / dca-target02
```

먼저 신규 Incident 생성 후 State Machine에서 다음 상태가 표시됨을 확인했다.

```text
INVESTIGATING
```

이후 Escalation API에 다음 상태를 입력했다.

```text
L3 / ESCALATION_REQUIRED
```

Frontend Polling 결과:

```text
INVESTIGATING
    ↓
ESCALATING
```

전환을 확인했다.

이후 동일 Incident에 다음 Physical Recovery 상태를 순차 적용했다.

```text
L4 / SPARE_ACTIVATING
L5 / PXE
L5 / CONFIGURING
L5 / READY
```

최종 `READY` 상태에서 Incident State Machine이 `VERIFYING` 단계로 전환되는 흐름을 검증했다.

Day 7 C 검증에서 실제 L3~L5 장비 제어는 수행하지 않았으며, C Escalation API 상태를 이용해 Platform / Visualization 경로를 검증했다.

---

## 6. Incident Close API

최종 Verification 이후 Incident를 명시적으로 종료할 수 있도록 Backend에 다음 API를 추가했다.

```text
POST /incidents/{incident_id}/close
```

Close 처리 시:

```text
Incident status  → CLOSED
ended_at         → 현재 시각 기록
Action           → CASE_CLOSED / CLOSED
```

CASE_CLOSED Action의 details에는 Physical Recovery Verification 완료 내용을 기록한다.

---

## 7. CASE CLOSED 및 Recovery Time UI

Incident History의 현재 Incident가 `CLOSED` 상태가 되면 State Machine의 마지막 단계가 활성화되도록 구성했다.

최종 결과 UI:

```text
FINAL RESULT
CASE CLOSED

Recovery Time
Xm Ys
```

Recovery Time은 Incident의 `started_at`과 `ended_at` 차이를 기준으로 계산한다.

사용자 요청에 따라 Day 7 마무리 시점에는 최종 `CLOSED / CASE CLOSED / Recovery Time` 화면 검증을 완료한 것으로 간주하고 문서화했다.

---

## 8. 스타일 구성

Day 7 전용 스타일을 다음 파일로 분리했다.

```text
frontend/src/day7.css
```

포함 스타일:

- Incident State Machine
- active / complete / pending 단계
- Rack `FAILED`
- Rack `SPARE`
- Rack `RECOVERING`
- Rack `READY`
- Final CASE CLOSED Card
- Recovery Time
- 반응형 Layout

`App.jsx`에서 `day7.css`를 import하여 기존 Day 5/6 UI와 함께 적용한다.

---

## 9. Day 7 C와 B/A 통합 범위 구분

Day 7 C에서 완료한 범위:

```text
Incident Lifecycle 시각화
Timeline 자동 Polling
Escalation → State Machine 연동
Rack Physical Recovery 상태 시각화
VERIFYING / CLOSED 상태 표현
CASE CLOSED / Recovery Time
```

실제 B의 L3~L5 Physical Infrastructure adapter를 통한 자동 장비 제어 및 실제 PXE Rebuild Trigger는 별도 통합 단계에서 검증한다.

따라서 다음을 구분한다.

```text
C Platform / Visualization 구현       : 완료
B → 실제 PXE 자동 실행 E2E 통합       : 후속 통합 검증
```

---

## Day 7 C 최종 결과

- Incident State Machine 구현
- `DETECTED → INVESTIGATING → ROOT_CAUSE_FOUND → RECOVERING → ESCALATING → VERIFYING → CLOSED` 시각화
- Timeline 2초 자동 Polling 구현
- Day 6 Escalation Polling과 Lifecycle 연동
- Parent App으로 Platform State 전달
- Rack Overview `FAILED / SPARE / RECOVERING / READY` 상태 표현
- `INVESTIGATING → ESCALATING` 실제 UI 전환 확인
- `READY → VERIFYING` Physical Recovery UI 흐름 구성
- Incident Close API 구현
- `CASE_CLOSED` Action 저장
- `CLOSED / CASE CLOSED / Recovery Time` 최종 UI 구현
- Day 7 전용 CSS 분리
- React Production Build 성공 확인
- 실제 B→PXE 자동연계는 후속 통합 검증 항목으로 분리

**Day 7 C — Incident Lifecycle·Physical Recovery Timeline·Rack 상태·CASE CLOSED 시각화 구현 완료**
