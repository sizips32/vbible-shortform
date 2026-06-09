# V-Bible Shorts — 작업 재개 노트 (2026-06-09)

## 완료 (검증됨)
- **5인 캐스팅**: 소스 5장 → Higgsfield 업로드(mediaId) → Elements(elementId). `assets/reference-media.json` 각 ref에 기록.
  - 시온 `c3af5fc8-8135-4639-a122-61b4cc898408` / 엄마 `6d8015a6-e737-4f76-8660-0aa37f2f31f3` / 하은 `21283476-f59f-4de2-aa2e-ae487b0afdb2` / 도현 `4ac11a0f-cafc-4259-affb-1fec64c3a06c` / 민준 `675e8e85-42cc-4081-847b-65f2051decc7`
  - 프롬프트에 `<<<elementId>>>` 임베드로 인물 고정. 다중 인물 = placeholder 여러 개.
- **키프레임 베이스라인**: `assets/keyframes/solo_*.png` (5인 단독). 다중 인물 테스트 `assets/test-shots/test_sion_haeun.png`.
- **i2v**: `seedance_2_0` 검증, `assets/clips/clip_sion_haeun_5s.mp4`.
- **한국어 립싱크 파이프라인 (핵심, 검증 완료)**:
  `한국어 TTS(wav/mp3) → media_upload(type=audio) → media_confirm → generate_video(model='wan2_7', medias:[{role:start_image,토킹헤드 키프레임},{role:audio,TTS media_id}])`
  - 샘플 `assets/clips/lipsync_sion_say_5s.mp4` — 오디오 한국어 보존(transcribe 일치)+입모양 동기화 확인. 7.5크레딧/720p·5s.
  - 토킹헤드 키프레임 예: 시온 job `cfe4355a-6353-4aef-b0fa-671233b30e9c`.
  - 제약: 립싱크는 **화자 1명/컷** → 대화는 화자별 클로즈업 단독 컷으로 분리.

## TTS — 해결됨 ✓ (2026-06-09)
- **ElevenLabs 키 복구**: `~/.config/hyperframes/.env` `ELEVENLABS_API_KEY` 교체·검증(200). 정상 키 51자. 입력 헬퍼 `scripts/set-eleven-key.sh`(hidden read). ⚠ 붙여넣기 중복 시 값 2배(102자)→401, 앞 51자만 남기면 복구.
- **5인 보이스 확정**(eleven_multilingual_v2): 시온=Will `bIHbv24MWmeRgasZH58o` / 엄마=Sarah `EXAVITQu4vr4xnSDxMaL` / 하은=Gigi `jBpfuIE2acCO8z3wKNLl` / 도현=Josh `TxGEqnHWrfWFTfGW9XjX` / 민준=Charlie `IKne3meq5aSn9XLyUdCD`. 각 ref에 voiceId/voiceName/voiceSample/voiceSampleMediaId 기록.
- 샘플 `assets/tts/voices/*.mp3` 5종 + Higgsfield 오디오 애셋 업로드 완료(voiceSampleMediaId).
- `/v1/voices` 정상(계정 31 보이스) — 교체는 이름으로 ID 조회 후 재생성.
- (대안) 로컬 Voicebox.app은 Qwen MLX 버그(`Stream(gpu,6)`)로 보류 — 필요시 `chatterbox`(CPU) 엔진 시도.

## 양산 단계 (TTS 확정 후)
1. 1화 스크립트 → 씬별 한국어 대사(화자별 분리).
2. 화자별 토킹헤드 클로즈업 키프레임(`<<<elementId>>>`) 생성.
3. TTS → 립싱크 클립(wan2_7) 양산.
4. 클립 합성/편집 (Capcut: `codex/capcut` 브랜치, 또는 hyperframes).

## 비용
잔액 ~1230크레딧. 키프레임 1.5/장, 립싱크 7.5/5s, i2v(seedance) 22.5/5s.

## 정책
모든 인물 대사·나레이션 **한국어 필수**. 영상 모델 자동 오디오 금지(한국어 보장 못 함). `reference-media.json meta.dialoguePolicy`·`meta.lipsyncPipeline` 참조.
