---
name: vbible-pipeline
description: V-Bible for Students 대본→영상 자동화 오케스트레이터. **사용자가 제공한 대본(문서 파일 또는 문장/텍스트)**을 받아 씬분할→Elements 키프레임→한국어 TTS·립싱크→합성·업로드까지 7단계로 자동 진행하며 게이트·비용·일관성을 강제한다. "이 대본으로 영상 만들어", "대본 줄게 영상 제작", "V-Bible 영상 만들어", "성경 쇼츠 제작", "에피소드 만들어", "다음 화", 또는 재실행·재개·부분 수정("키프레임만 다시", "렌더 재실행", "이전 결과 개선") 요청 시 사용. 주제·기획은 사용자가 정하므로 임의 창작하지 않는다. 단순 질문은 직접 응답.
allowed-tools: Read, Write, Bash, Skill, Agent
---

# vbible-pipeline — V-Bible 에피소드 오케스트레이터

V-Bible 한 편을 7단계로 양산한다. 각 전문 작업은 `.claude/agents/`의 vbible-* 에이전트에 위임하고, 게이트·비용·정합성은 오케스트레이터가 강제한다.

**실행 모드:** 서브 에이전트 + 오케스트레이터(순차 파이프라인, 비용 게이트). 에이전트 호출은 `Agent` 도구, `subagent_type`에 에이전트명.

**모델 티어링(호출부에서 override가 정본):** 기본 `model: "opus"`. **예외 = 4단계 prompt만 `model: "sonnet"`**(기계적 i2v 프롬프트 작성 — 비용·지연↓). vbible-qa는 지각 드리프트 판단(안경·머리색·스타일)이 핵심이라 **opus 유지**(다운그레이드 금지).

**상태 헬퍼:** `python3 lib/state.py` (프로젝트 루트에서). state.json 직접 편집 금지 — 모든 전이는 헬퍼로만. 크레딧 감사 `credits <slug>`(clips.json 파생, 별도 원장 없음), 완료 기록 `finalize <slug>`(episodes-index.json).

**합성·검증 헬퍼:** `python3 lib/assemble.py projects/<epSlug>` → `PREVIEW.mp4`(1080×1920·-14 LUFS) + `PREVIEW.srt`(한국어 자막 사이드카). `python3 lib/qa_checks.py <projectDir> --stage N` = 결정론 QA(불변식 기계 판정).

**단일 진실 원천:** `projects/vbible-students/assets/reference-media.json`(채널 바이블). 모든 단계가 공유. 시작 시 `vbible-foundation` 스킬을 읽어 불변식을 적재한다.

---

## Phase 0: 컨텍스트 확인 (항상 먼저)

1. `vbible-foundation` 스킬을 Skill 도구로 읽는다(불변식 적재). 채널 바이블이 없으면 중단·안내.
2. **대본 입력 판별** + 요청 분기:
   - **재개**: `--resume <epSlug>` 또는 "재개/이어서" → `python3 lib/state.py resume <epSlug>` → currentStep부터.
   - **부분 재실행**: "키프레임만/렌더만 다시" + 해당 epSlug 존재 → 그 단계 에이전트만 재호출(아래 재호출 지침). 기존 산출물 보존.
   - **신규 (대본 제공)** — 입력 유형 자동 판별:
     - **대본 파일 경로**(.md/.txt 등 존재 파일) → 그 파일을 정규 대본 입력으로 사용.
     - **인라인 대본 텍스트**(긴 다중 행) → 그대로 대본 입력으로 사용.
     - **짧은 문장/로그라인** → 1단계 intake에서 한국어 대본으로 확장.
     - epSlug 생성(`vbible-ep-<NN>-<제목-slug>`, 영문 소문자·하이픈, 대본 제목에서 추출). `python3 lib/state.py init <epSlug> --logline "<제목 또는 첫 문장>"`. 코드 1(존재)이면 다른 slug 또는 --resume 안내.
   - **입력 없음**: "대본(문서 또는 문장)을 주세요"라고 사용법 안내. 주제·기획은 임의 창작하지 않는다.
3. `mcp__higgsfield.balance`로 잔액 확인, 편당 650 예산 대비 고지.

## 단계 실행 공통 규칙
- 각 게이트 단계: 에이전트 산출 → 사용자 제시 → 승인 → `set-output` → `approve` → `advance`(코드 0이면 다음, 코드 3이면 차단·재확인).
- 데이터 전달: **파일 기반**(`projects/<epSlug>/briefs|assets|clips/`) + 반환값 요약. 중간 산출물 보존(감사 추적).
- 비용 발생 단계(3·5)는 에이전트가 생성 전 비용 표 고지·승인. 오케스트레이터는 승인 없이는 advance 안 함.
- QA(2층): 단계 2·3·5 직후 **① 먼저 `python3 lib/qa_checks.py projects/<epSlug> --stage N`**(결정론: elementId 일치·화자1명/컷·한국어·예산합산·9:16/길이) → 통과 시 **② `vbible-qa`(opus)**(지각: 캐릭터 드리프트·안경·머리색·스타일 — 이미지를 실제로 본다). 둘 중 하나라도 FAIL이면 담당 에이전트 수정 후 재검증(이슈 = 단계 미완료).

---

## 1단계 — intake (게이트): 대본 수용·정규화
1. `Agent(subagent_type="vbible-scriptwriter", model="opus")` — Phase 0에서 판별한 **대본 입력**(파일 경로 / 인라인 텍스트 / 짧은 문장)과 epSlug 전달.
   - 완성 대본 → **원문 존중**, 한국어 정규화·화자 표기만 정돈 → `briefs/script.md`.
   - 짧은 문장 → 한국어 대본으로 확장 → `briefs/script.md`.
2. `Agent(subagent_type="vbible-theology-reviewer", model="opus")` — script.md 성경 검증. 사용자 완성 대본은 표현 변경 최소(이슈는 사용자에게 위임). REVISE면 처리 후 재검증.
3. 사용자에게 script.md 제시·승인 → set-output 1 → approve 1 → advance.

## 2단계 — breakdown (게이트): 씬·화자분리·샷리스트
1. `Agent(subagent_type="vbible-scriptwriter", model="opus")` — 승인된 script.md → `briefs/shotlist.md`(씬분할 + 화자분리 대사표 + 컷 유형). 컷 수는 대본 길이에 따라 가변.
2. **결정론 QA** `python3 lib/qa_checks.py projects/<epSlug> --stage 2` → 통과 후 `Agent(subagent_type="vbible-qa", model="opus")` — 2단계 체크(화자분리·립싱크 1명/컷·한국어·화자 매칭). FAIL이면 수정·재검증.
3. 사용자 승인 → set-output 2 → approve 2 → advance.

## 3단계 — style (게이트, 비용)
1. `Agent(subagent_type="vbible-visual-director", model="opus")` — Elements 키프레임 생성(씬 + 화자별 토킹헤드). 에이전트가 비용 고지·승인 후 `generate_image`. → `briefs/keyframes.json`.
2. **결정론 QA** `python3 lib/qa_checks.py projects/<epSlug> --stage 3`(elementId 일치·placeholder 수=인물 수·한국어) → 통과 후 `Agent(subagent_type="vbible-qa", model="opus")` — 3단계 지각 검증(토킹헤드 발화 포즈·forbiddenVariations: 도현 안경·시온 무안경·머리색·스타일 드리프트를 **이미지에서 확인**). FAIL이면 흔들린 컷 재생성.
3. 사용자가 키프레임 일관성 확정 → set-output 3 → approve 3 → advance.

## 4단계 — prompt (자동, 게이트 없음)
`Agent(subagent_type="vbible-visual-director", model="sonnet")` — **i2v 씬 컷만** 한국어 프롬프트 설계 → `briefs/prompts.json`(립싱크 컷은 제외, 컷 유형만 표기). 기계적 작업이라 sonnet으로 충분(티어링). set-output 4 → advance.

## 5단계 — render (게이트, 비용)
1. `Agent(subagent_type="vbible-render-engineer", model="opus")` — 한국어 TTS + wan2_7 립싱크(화자1명/컷) + seedance i2v(무음). 에이전트가 컷별·총 크레딧 표 고지·승인 후 생성. → `assets/clips.json` + `clips/`.
2. **결정론 QA** `python3 lib/qa_checks.py projects/<epSlug> --stage 5`(화자1명/컷·dialoguePolicy·예산합산≤650·매핑·PREVIEW 있으면 9:16/길이) → 통과 후 `Agent(subagent_type="vbible-qa", model="opus")` — 5단계 지각 검증(립싱크 한국어 음성 보존·무음 i2v·단체 씬 정체성 드리프트). FAIL이면 해당 컷 재렌더.
3. 사용자 승인 → set-output 5 → approve 5 → advance.

## 6단계 — curate (게이트)
오케스트레이터가 clips.json 결과를 사용자에게 제시, 컷별 채택/재생성 선별 → `briefs/selects.md`(사람용 표) **+ `briefs/selects.json`**(`{"order":["C1","C2",...]}` — 7단계 assemble가 소비하는 정본 순서; 컷 드롭/재배치 반영). 승인 → set-output 6 → approve 6 → advance.

## 7단계 — post (자동: 조립 → NLE 마무리)
1. **자동 합성** `python3 lib/assemble.py projects/<epSlug>` → `clips/PREVIEW.mp4`(1080×1920, 컷순서=selects.json, -14 LUFS 정규화) + `clips/PREVIEW.srt`(한국어 자막 사이드카). i2v 컷은 임베드 오디오 폐기·한국어 TTS 트랙만 먹싱(불변식 2-1 **기계 강제**), 립싱크 컷은 임베드(=한국어) 오디오 유지. selects.json 없으면 clips.json 순서 폴백. 크로스페이드는 `--crossfade 0.3` opt-in(자막 어긋남 경고). assemble 후 `qa_checks --stage 5`로 PREVIEW 9:16/길이 재확인.
2. **NLE 마무리(사람 ~10%)**: PREVIEW.mp4를 CapCut/hyperframes 임포트 → BGM·로고·성경구절·전환만 추가. 자막은 PREVIEW.srt 임포트(한국어, NLE에서만 — 영상 내 생성 금지). 9:16 유지.
3. **업로드 메타**: 제목(대본 제목/주제에서 도출), 설명, 고정 해시태그(#VBibleForStudents #학생바이블 #바이블칼리지 #성경공부 #기독교쇼츠 #BibleShorts), 오프닝/엔딩 고정 문구(사용자 대본이 별도 지정 시 그것 우선).
4. `projects/<epSlug>/briefs/post-checklist.md` Write. `python3 lib/state.py credits <epSlug>` 최종 크레딧 확인 → set-output 7 → advance(완료) → `python3 lib/state.py finalize <epSlug>`(episodes-index.json 실측 기록). 사용 크레딧·다음 화 안내.

---

## 에러 핸들링
| 상황 | 처리 |
|------|------|
| 에이전트 실패 | 1회 재시도. 재실패 시 그 산출물 없이 보고에 누락 명시, 사용자에게 위임. |
| 비용 미승인 | 생성 차단. 절대 임의 진행 안 함(타협 불가). |
| QA/theology FAIL | 담당 에이전트 수정 → 재검증. 통과 전 advance 금지. |
| state advance 코드 3 | 게이트 미승인 — 진행 차단, 사용자 재확인. |
| ElevenLabs 키 없음/401 | `scripts/set-eleven-key.sh` 안내(중복 붙여넣기 시 102자→앞 51자만). 복구 전 TTS 중단. |
| 상충 데이터 | 삭제 말고 출처 병기, 사용자 판단. |

## 테스트 시나리오
- **대본 파일 입력**: 사용자가 `script.md`(완성 대본) 제공 → 1단계 intake에서 원문 존중·정규화 → 2단계 breakdown 씬·화자분리 → 3~7단계 순차, 게이트 승인, 편당 ≤650크레딧, 한국어 립싱크 확인 → post-checklist 완료.
- **문장 입력(확장)**: "하은이 시온에게 기도가 뭐냐고 묻는 짧은 장면" 한 문장 → intake에서 한국어 대본 확장 → theology PASS → 이후 동일.
- **에러 흐름(게이트 차단)**: 3단계에서 도현 안경 누락 → vbible-qa FAIL → visual-director 해당 컷 재생성 → 재검증 PASS → advance. 미승인 상태로 advance 시 코드 3 → 차단 확인.

## 후속 작업
- 부분 재실행: "5단계만 다시" → 해당 에이전트만, 기존 briefs/assets Read 후 변경분만.
- 전 단계 산출물 존재 시 에이전트는 Read 후 개선(전체 재작성은 새 입력 시만).
