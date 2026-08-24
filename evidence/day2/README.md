# Day 2 Diagnostic Evidence

`diagnostic/`의 JSON 파일은 `automation/ansible/playbooks/day2_diagnostic.yml`이 각 managed host에서 수행한 read-only 자동 진단 결과입니다. 기존 Evidence JSON schema를 유지하며, 호스트별 파일에는 다음 증거가 포함됩니다.

- NIC 링크와 Mellanox QSFP+ 장치 존재 여부, `mlx4_en` 드라이버 및 필수 Kernel Module 상태
- Data IP, Gateway, Route 및 DNS 구성과 접근 상태
- 각 managed host에서 PXE Server까지의 ICMP reachability
- systemd failed unit, filesystem 사용량, firewall, CPU load 및 memory 상태
- 설정된 service와 TCP port diagnostic 결과

파일별 대상:

- `dca-target01.json`: Ubuntu target 서버 자동 진단 Evidence
- `dca-target02.json`: Rocky target 서버 자동 진단 Evidence
- `dca-spare01.json`: `spare_rebuild=true`인 Rocky spare 서버 자동 진단 Evidence

각 check의 `status`는 `PASS`, `WARN`, `FAIL`, `UNKNOWN`, `SKIP` 중 하나이며, `detail`에는 판정에 사용한 명령 결과 요약이 기록됩니다. 내부 IP, MAC address, hostname은 인프라 상태를 증명하기 위한 Evidence의 일부입니다.
