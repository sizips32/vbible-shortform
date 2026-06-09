---
name: vbible-foundation
description: V-Bible for Students 채널의 공유 컨텍스트·불변식 레이어. 모든 vbible-* 에이전트와 vbible-pipeline이 작업 전 가장 먼저 로드한다. 캐릭터·보이스·Elements·한국어 TTS·예산·포맷의 단일 진실 원천(reference-media.json)을 가리키고, 절대 위반 불가한 제작 불변식을 정의한다. "V-Bible", "비바이블", "성경 쇼츠", "5인 캐릭터", "시온/엄마/하은/도현/민준", "립싱크 영상" 작업 시 반드시 이 스킬을 먼저 읽어 불변식을 적용한다.
allowed-tools: Read
---

# vbible-foundation — V-Bible 채널 헌법 (공유 컨텍스트)

V-Bible for Students 영상 제작의 모든 판단이 출발하는 단일 컨텍스트 레이어. **어떤 에이전트도, 어떤 단계도 이 불변식을 우회할 수 없다.** 작업 시작 전 항상 이 파일과 채널 바이블을 읽는다.

## 0. 단일 진실 원천 (Single Source of Truth)

채널 바이블 = `projects/vbible-students/assets/reference-media.json`.

5인 캐릭터의 elementId·voiceId·characterSheet·voiceProfile·정책이 모두 여기 있다. **값을 스킬/에이전트 본문에 복사하지 마라 — 항상 reference-media.json을 Read로 새로 읽어라.** 복사본은 드리프트(불일치)를 낳는다. 이 원칙이 "지속가능성"의 핵심이다.

작업 재개 노트 = `projects/vbible-students/RESUME.md` (검증된 파이프라인 이력·잔여 작업).

**메커니즘 정본 분리(통합 원칙):** (1) 채널 데이터·V-Bible 메커니즘 = reference-media.json(`refs[]` + `meta.*`). (2) 범용 제작 메커니즘(키프레임·렌더·일관성 HOW) = higgsfield-shortform 엔진 스킬 `short-style`/`short-render`/`short-consistency`(Elements·한국어 TTS·wan2_7 지원으로 업그레이드됨). 이 foundation은 **둘을 가리키는 얇은 인덱스 + enforcement 체크리스트 + V-Bible 전용 설정(포맷·예산·레이아웃)**일 뿐, 메커니즘을 재기술하지 않는다.

## 1. 5인 캐릭터 (요약 — 상세·고정값은 reference-media.json)

| 이름 | 역할 | 관계 | 핵심 식별자 (절대 변경 금지) |
|------|------|------|------|
| 시온 | 주인공·기본 내레이터 | 장남(오빠) | 베이지 오버핏 후드 + 다크브라운 단발 + 헤이즐눈 |
| 엄마 | 어머니 | 시온·하은 모친 | 턱선 브라운 보브 + 크림 7부상의 + 토프 롱스커트 |
| 하은 | 여동생(질문자) | 막내 | 네이비 점퍼스커트 + 흰 블라우스 + 흰 무릎양말 |
| 도현 | 친구(사색형) | 시온 학교친구 | **검은 사각 안경(필수 식별자)** + 네이비 브이넥 니트 |
| 민준 | 친구(활기형) | 시온 학교친구 | 카멜 라운드 니트 + 밝은 갈색 볼륨머리 + 환한 미소 |

각 캐릭터의 `forbiddenVariations`(머리색/의상색/안경/성인화/화면내 글자 금지)는 reference-media.json `refs[].characterSheet.forbiddenVariations`에 있다. **이를 위반한 산출물은 미완료다.**

## 2. 절대 불변식 (위반 시 = 작업 미완료)

각 불변식은 **enforcement 대상 규칙**이다. **메커니즘 상세·고정값의 정본은 reference-media.json `meta.*`**이며(아래 "정본" 열), 범용 제작 메커니즘은 higgsfield-shortform 엔진 스킬(`short-style`/`short-render`/`short-consistency`)을 따른다. 아래 표는 규칙 요약 + 정본 위치일 뿐 — **세부가 바뀌면 이 표가 아니라 정본을 보라.** (중복 기술 금지 = 드리프트 방지.)

| # | 불변식 (규칙) | 정본 위치 |
|---|------|----------|
| 2-1 | 모든 대사·나레이션 **한국어**. 영상 모델 자동 오디오 금지 → 무음 생성 + **ElevenLabs TTS 별도 트랙**. | `meta.dialoguePolicy`(엔진·키 경로·audioSource), `refs[].voiceId`/`voiceProfile`. 키 헬퍼 `projects/vbible-students/scripts/set-eleven-key.sh` |
| 2-2 | 캐릭터 고정 = Higgsfield **Elements**(`<<<elementId>>>` 임베드, 다중 인물=placeholder 여러 개), Soul 미사용. | `meta.elementUsage`, `meta.elementSupportedModels`(키프레임 기본 `nano_banana_2`), `refs[].elementId` |
| 2-3 | 세로 **9:16**, soft-anime 스타일 락. **화면 내 글자 절대 금지**(자막은 NLE). | `meta.styleLock`, `meta.negativePrompt` |
| 2-4 | 립싱크 = **화자 1명/컷**(토킹헤드 클로즈업). 다중 동시 발화 불가 → i2v 무음 + 오프스크린 음성. | `meta.lipsyncPipeline`(wan2_7 flow), `meta.i2vPipeline`(seedance_2_0 무음) |
| 2-5 | 편당 **≤650 크레딧**, 월 3,000(4편+예비400). **생성 전 비용 고지·승인 필수**(승인 없는 지출 금지). | 단가: 키프레임 1.5/장, 립싱크 7.5/5s·720p, i2v 22.5/5s·720p. 잔액 `mcp__higgsfield.balance` |

## 3. 채널 포맷 (기본값 — 사용자 대본이 우선)

**대본은 사용자가 제공한다.** 주제·기획·구조는 사용자 대본이 정하며, 하네스는 그것을 임의로 창작하지 않는다. 아래는 **사용자가 짧은 문장만 줘서 확장이 필요할 때의 기본 제안값**일 뿐, 완성 대본에 강제하지 않는다.

- 기본 길이 60~90초, 나레이션 180~250자, 세로 9:16.
- 기본 포맷(예): 하나의 질문 + 핵심 키워드 3개 + 1문장 결론. (사용자 대본이 다른 구조면 그것을 따른다.)
- 기본 톤: 설교식 ❌ → 수업형 + 시네마틱 + 짧은 묵상 ✅. 타깃: 중·고등·대학생·청년부 초신자.
- 오프닝/엔딩 고정 문구가 필요하면 제안(예: "V-Bible for Students, 오늘의 1분 바이블 칼리지." / "성경을 알면, 삶을 보는 눈이 달라집니다.") — 사용자 대본이 지정 시 그것 우선.

## 4. 워크스페이스 레이아웃

```
projects/vbible-students/              # 채널 홈 (공유)
  assets/reference-media.json          # ★ 채널 바이블 (단일 진실 원천)
  assets/keyframes/solo_*.png          # 5인 베이스라인 키프레임
  assets/tts/voices/*.mp3              # 보이스 샘플
  RESUME.md                            # 검증 파이프라인 이력
projects/vbible-ep-XX-<slug>/          # 에피소드별 워크스페이스 (slug = state.py 단위)
  state.json                           # lib/state.py 전용 (직접 편집 금지)
  briefs/{concept,shotlist}.md, {keyframes,prompts,clips}.json, post-checklist.md
  clips/                               # 렌더 산출물
```

채널 바이블은 **모든 에피소드가 공유**한다(복사하지 않음). 에피소드는 별도 slug.

## 5. 단계 맵 (V-Bible ↔ 7단계 파이프라인)

| 단계 | 게이트 | 담당 에이전트 | 핵심 |
|------|--------|--------------|------|
| 1 intake | ✓ | vbible-scriptwriter → **vbible-theology-reviewer** | **사용자 대본 수용·정규화**(문장이면 확장) / 성경 검증 |
| 2 breakdown | ✓ | vbible-scriptwriter | 씬분할 + 화자분리 대사 + 샷리스트 |
| 3 style | ✓ | vbible-visual-director | Elements 키프레임(씬 + 화자별 토킹헤드) |
| 4 prompt | — | vbible-visual-director | i2v 컷 한국어 프롬프트(립싱크 컷은 제외) |
| 5 render | ✓ | vbible-render-engineer | 한국어 TTS + wan2_7 립싱크 + seedance i2v (비용 게이트) |
| 6 curate | ✓ | (오케스트레이터) | 컷 선별 |
| 7 post | — | (오케스트레이터) | 합성·자막·BGM·업로드 메타 |

**vbible-qa**는 단계 2·3·5 직후 점진적으로 경계면을 검증한다(존재 확인이 아니라 불변식 위반 탐지).

## 6. 자가 점검 (모든 에이전트 공통)
- [ ] reference-media.json을 **이번 작업에서 새로 Read** 했는가? (기억/복사본 사용 금지)
- [ ] 대사·나레이션이 전부 한국어인가? 영상 모델 자동 오디오를 쓰지 않았는가?
- [ ] 다중 인물 컷에 `<<<elementId>>>` placeholder가 인물 수만큼 있는가?
- [ ] forbiddenVariations(안경·머리색·의상색·성인화·화면내 글자)를 위반하지 않았는가?
- [ ] 생성 전 비용을 고지하고 승인을 받았는가? 편당 650크레딧 한도 안인가?
