# TODOs

## 1) Orphan 가시성 및 복구 UX 추가 (P3-C)

- What: 라이브러리 스캔 시 `stems/`는 있으나 `<uuid>.json`이 없는 orphan 상태를 경고 카드로 노출하고, `재시도`(메타 재생성 시도) / `정리`(삭제) 액션을 제공한다.
- Why: 메타 atomic write 실패 시 사용자 관점에서 결과가 사라진 것처럼 보이는 silent failure를 막는다.
- Pros: 장애 재현성과 복구 가능성이 올라가고, 사용자 문의/혼선이 줄어든다.
- Cons: 라이브러리 상태 모델과 UI 분기(경고 카드/버튼/실패 상태)가 늘어난다.
- Context: `docs/phase-3.md` 리스크 섹션의 메타 corruption 항목, `GSTACK REVIEW REPORT`의 critical gap(오프안 UX 가시성).
- Depends on / blocked by: P3-B의 orphan 탐지 규칙 고정, `list_projects` API가 orphan 상태를 표현할 수 있어야 함.

## 2) assetProtocol/workdir 일치 검증 자동화 (P3-A 후속)

- What: 현재 수동 검증 항목(`convertFileSrc`로 WAV 1개 로드 성공)을 자동 체크 스크립트 또는 통합 테스트로 고정한다.
- Why: `$APPLOCALDATA` scope와 실제 `app_local_data_dir()/yt-split` workdir 불일치 회귀를 릴리즈 전에 잡기 위해.
- Pros: 경로/권한 회귀를 조기에 탐지하고, 환경별 편차(dev/prod) 검증이 반복 가능해진다.
- Cons: 테스트 환경에서 샘플 오디오/경로 셋업이 필요해 초기 구성 비용이 든다.
- Context: `docs/phase-3.md` 리스크 섹션의 `$APPLOCALDATA` 일치 검증 항목.
- Depends on / blocked by: P3-A 구현 완료 및 테스트 훅(샘플 WAV, Tauri 실행 경로) 준비.

## 3) Phase2 -> Phase3 마이그레이션 가이드 보강 (P3-D 문서)

- What: 기존 `./output` 사용자 대상 이전 절차(어디서 무엇을 복사/유지/삭제할지, 재스캔 가능 여부)를 README 또는 `docs/phase-3.md` 부록으로 명확화한다.
- Why: 업그레이드 후 “기존 곡이 안 보인다”는 혼선을 줄이고, 지원/문의 대응을 표준화하기 위해.
- Pros: 사용자 기대치가 명확해지고, 릴리즈 노트와 지원 응답 품질이 좋아진다.
- Cons: 릴리즈마다 문서 최신성 점검 포인트가 하나 늘어난다.
- Context: `docs/phase-3.md` 리스크 섹션 Migration window 항목.
- Depends on / blocked by: P3-D 결정(자동 마이그레이션 없음) 유지, 최종 저장 경로 정책 확정.
