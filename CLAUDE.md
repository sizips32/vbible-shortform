# V-Bible for Students — 프로젝트 가이드

학생용 성경 쇼츠(60~90초, 세로 9:16) 제작 프로젝트. Higgsfield + ElevenLabs 한국어 TTS 기반.

## 하네스: V-Bible 에피소드 제작

**목표:** **사용자가 제공한 대본(문서 또는 문장)**을 입력으로 받아, 5인 캐릭터 일관성과 한국어 대사 정책을 강제하며 영상까지 자동 제작한다. 주제·기획은 사용자가 정하고 하네스는 창작하지 않는다.

**트리거:** "이 대본으로 영상 만들어", 대본 파일/텍스트 제공, V-Bible 영상/에피소드 제작·재실행·재개·부분 수정 요청 시 `vbible-pipeline` 스킬을 사용하라. 작업 전 `vbible-foundation` 스킬로 불변식을 적재한다. 단순 질문은 직접 응답 가능.

**핵심 불변식 (위반 = 미완료 — 상세는 `vbible-foundation`):**
- 단일 진실 원천 = `projects/vbible-students/assets/reference-media.json`. 값 복사 금지, 항상 새로 Read.
- 모든 대사·나레이션 **한국어**. 영상 모델 자동 오디오 금지 → ElevenLabs TTS 별도 트랙.
- 캐릭터 고정 = Higgsfield **Elements**(`<<<elementId>>>`), Soul 미사용.
- 립싱크 = `wan2_7`, 화자 1명/컷. i2v = `seedance_2_0` 무음. 키프레임 = `nano_banana_2`.
- 화면 내 글자 금지(자막은 NLE). 편당 ≤650 크레딧 — 생성 전 비용 승인 게이트.

**구조:**
- `.claude/skills/vbible-foundation` — 채널 헌법·불변식(공유 컨텍스트).
- `.claude/skills/vbible-pipeline` — 7단계 오케스트레이터(에피소드 제작).
- `.claude/agents/vbible-*` — scriptwriter, theology-reviewer, visual-director, render-engineer, qa.
- `lib/state.py` — 단계 게이트 상태머신(직접 편집 금지). `credits`(clips.json 파생)·`finalize`(episodes-index.json).
- `lib/assemble.py` — 7단계 자동 합성(ffmpeg): selects 순서 concat + i2v 무음·TTS 먹싱(불변식 2-1 기계 강제) + -14 LUFS → `PREVIEW.mp4` + 한국어 `.srt`.
- `lib/qa_checks.py` — 결정론 QA(elementId·화자1명/컷·한국어·예산·9:16/길이). vbible-qa(opus)는 지각 드리프트 판단만.
- `tests/test_v2.py` — 순수함수·QA·불변식 2-1 단언(`python3 -m unittest discover -s tests`).

**엔진:** 범용 숏폼 메커니즘은 `higgsfield-shortform` 플러그인(`../my_higgsfield`, Elements·한국어 TTS·립싱크 지원으로 업그레이드됨)을 재사용한다. 설치: `/plugin marketplace add ../my_higgsfield` → `/plugin install higgsfield-shortform`. 미설치여도 V-Bible 레이어는 자기완결적으로 동작한다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-06-09 | 초기 구성 | 전체 | 검증된 파이프라인(RESUME/reference-media)을 하네스로 코드화 |
| 2026-06-09 | 진입점 전환: 주제 창작 → **사용자 대본 입력** | pipeline·scriptwriter·foundation·state.py | "대본(문서/문장) 주면 영상까지 자동화" 요구. 1단계 intake(대본 수용·확장), 2단계 breakdown(씬·화자분리). 4주 시리즈 하드코딩 제거 |
| 2026-06-10 | **v2 — 7단계 자동화 + QA 2층화** | assemble.py·qa_checks.py·state.py·pipeline·qa·foundation | 7단계 수동 갭 제거: `assemble.py`가 PREVIEW.mp4+.srt 자동 합성(i2v 무음+TTS 먹싱으로 불변식 2-1 기계 강제), `qa_checks.py`가 결정론 검사를 vbible-qa(opus 지각 판단)에서 분리, state `credits`/`finalize`(episodes-index), 4단계 prompt만 sonnet 티어링. ep-00 실증: 테스트 16/16, PREVIEW 1080×1920/50s, 크레딧 123 |
