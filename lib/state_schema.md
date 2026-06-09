# state.json 스키마

워크스페이스: `projects/<slug>/state.json` (런타임 산출물, git 미추적). 모든 상태 전이는 `lib/state.py`로만 수행한다. 마크다운 스킬/커맨드가 직접 편집하지 않는다.

```json
{
  "slug": "subway-umbrella",
  "logline": "지하철에서 우산을 건네는 낯선 사람",
  "currentStep": 1,
  "createdAt": "2026-06-01T00:00:00",
  "steps": {
    "1": {"name": "intake",    "gate": true,  "status": "pending", "gateApproved": false, "output": null},
    "2": {"name": "breakdown", "gate": true,  "status": "pending", "gateApproved": false, "output": null},
    "3": {"name": "style",  "gate": true,  "status": "pending", "gateApproved": false, "output": null},
    "4": {"name": "prompt", "gate": false, "status": "pending", "gateApproved": false, "output": null},
    "5": {"name": "render", "gate": true,  "status": "pending", "gateApproved": false, "output": null},
    "6": {"name": "curate", "gate": true,  "status": "pending", "gateApproved": false, "output": null},
    "7": {"name": "post",   "gate": false, "status": "pending", "gateApproved": false, "output": null}
  }
}
```

## 서브커맨드 계약 (`python3 lib/state.py`)

| 명령 | 동작 | 종료코드 |
|---|---|---|
| `init <slug> --logline TEXT [--force]` | 워크스페이스+state.json 생성 (존재 시 --force 없으면 거부) | 0 / 1(이미존재) |
| `read <slug> [--field NAME]` | state JSON 또는 특정 필드 출력 | 0 / 2(없음) |
| `set-output <slug> <step> --file PATH [--no-verify]` | PATH 존재 확인(없으면 거부) 후 step.status=done, step.output=PATH | 0 / 2 / 5(파일없음) |
| `approve <slug> <step>` | step.gateApproved=true (step.status=done 선행 필수) | 0 / 4(미완료) |
| `advance <slug>` | currentStep S: status=done & (gate=false 또는 gateApproved) → currentStep=S+1 출력. 아니면 차단 | 0 / 3(차단) |
| `resume <slug>` | currentStep과 status를 `STEP\tNAME\tSTATUS` 형식으로 출력 | 0 / 2 |
| `credits <slug>` | clips.json에서 컷별·총 creditsUsed 합산 출력(별도 원장 없음 — 드리프트 0). 650 초과 시 OVER LIMIT | 0 / 2(clips없음) / 7(초과) |
| `finalize <slug>` | 완료 에피소드를 `projects/vbible-students/episodes-index.json`에 실측값(slug·logline·일자·credits·runtimeSec·stepsDone)으로 기록. 같은 slug는 갱신 | 0 / 2 |

게이트 강제 = `advance`의 종료코드 3. 오케스트레이터는 `advance` 성공(코드 0) 시에만 다음 단계로 넘어간다.

**파생 데이터 원칙:** `credits`/`finalize`의 크레딧·런타임은 `clips.json`을 **읽어 합산**할 뿐 state.json에 복사 저장하지 않는다(clips.json = 렌더 SSOT). episodes-index.json은 측정값만 담고 재생성 횟수·소요시간 등 미측정 값을 날조하지 않는다.
