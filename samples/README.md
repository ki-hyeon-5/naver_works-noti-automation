# 합성 테스트 픽스처
모든 정보는 가상 데이터입니다. 사내 토큰/실제 알람/개인정보를 이 디렉터리에 넣거나 커밋하지 마세요.
- `grafana-synthetic-input.txt`: 라벨 없는 값만 포함한 **줄바꿈이 존재하는** 3건 입력. 완전 무경계 접합문은 이 샘플의 검증 범위가 아닙니다.
- `grafana-mapping-synthetic.json`: 합성 Grafana 매핑 1건(이 샘플에서는 매칭되지 않음).
- `n3r-mapping-synthetic.json`: 합성 N3R 매핑 2건 (`bill-db-01`, `bill-db-02`).
- `expected-results.json`: 3건 중 1건 NoData 제외, 2건 각각 `[N3R]` 태그가 나오는 근거 포함.
- 파서 실제 클립보드 정확성은 원본 샘플 미제공으로 별도 현장 검증이 필요합니다.
