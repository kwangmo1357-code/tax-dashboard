# 회계·세무 대시보드 (GitHub Pages + Claude API)

매일 아침 GitHub Actions가 법제처 Open API에서 세법 개정·국세청 해석례·조세심판원 재결례를 가져오고,
**새로 나온 건만** Claude API로 요약해서 GitHub Pages에 배포합니다.

## 구조

| 파일 | 역할 |
|---|---|
| `scripts/update_data.py` | 법제처 조회 → Claude 요약 → 법정기한 계산 → `site/data.json` 생성 (Python 표준 라이브러리만 사용) |
| `site/index.html` | 화면. `data.json`·`impact.json`만 읽음 (API 키 없음) |
| `site/impact.json` | **중견 제조 상장사 영향 분석** (수기 관리). 세법 개정·심판례를 재무제표/세무 영향·체크리스트로 정리 |
| `data/summaries.json` | 요약 캐시. 이미 요약한 건은 다시 호출하지 않음 |
| `.github/workflows/update.yml` | 매일 06:47 KST 실행 + 수동 실행 + Pages 배포 |

## 설정 순서

| 단계 | 어디서 | 할 일 |
|---|---|---|
| 1 | open.law.go.kr | 회원가입 → OPEN API 신청. **OC 값** = 가입 이메일의 @ 앞부분. 활용 신청에서 `법령`, `중앙부처 1차 해석(국세청)`, `특별행정심판(조세심판원)` 체크 |
| 2 | console.anthropic.com | API Keys → Create Key → `sk-ant-...` 복사. Billing에서 크레딧 충전, Limits에서 월 사용 한도 설정 권장 |
| 3 | github.com | 새 저장소 생성 (예: `tax-dashboard`) → 이 폴더 전체 업로드 |
| 4 | 저장소 Settings → Secrets and variables → Actions | **Secrets**: `LAW_OC`, `ANTHROPIC_API_KEY` 등록 / (선택) **Variables**: `CLAUDE_MODEL` |
| 5 | 저장소 Settings → Pages | Source를 **GitHub Actions**로 선택 |
| 6 | 저장소 Actions 탭 | "대시보드 데이터 갱신 및 배포" → Run workflow → 완료 후 `https://<아이디>.github.io/tax-dashboard/` 접속 |

## 비용·보안 메모

| 항목 | 내용 |
|---|---|
| Claude 비용 | 첫 실행 때 약 100건 요약, 이후는 새 건만(보통 하루 0~10건). 기본 모델 `claude-haiku-4-5` 기준 월 몇백 원~몇천 원 수준 |
| API 키 | GitHub Secrets에만 저장되고, 공개 사이트와 `data.json`에는 들어가지 않음 |
| OC 값 | 링크를 만들 때 OC 값은 지움 |
| 공개 범위 | 무료 계정의 Pages는 공개 사이트. 회사 내부 정보(담당자·법인별 기한)는 넣지 말 것 |
| 휴일 | 주말과 고정 공휴일만 반영. 설·추석·대체공휴일은 `update_data.py`의 `HOLIDAYS_EXTRA`에 추가 |

## 수정 포인트

| 바꾸고 싶은 것 | 위치 |
|---|---|
| 추적 법령·관점 문구 | `update_data.py` → `LAW_FOCUS` |
| 검색어 / 주제 탭 분류 | `update_data.py` → `QUERIES` / `TOPIC_RULES` |
| 제외어 / 제조업 관련도 키워드 | `update_data.py` → `EXCLUDE` / `MFG_KEYS` |
| 영향 분석 카드 | `site/impact.json` → `items` (`basis`: 확인 / 확인 필요 / 분석) |
| 화면만 다시 확인 (API 호출 없이 재분류) | `python scripts/update_data.py --offline` |
| 실행 시각 | `update.yml` → `cron` (UTC 기준, KST −9시간) |
| 요약 문구 스타일 | `update_data.py` → `claude_summarize()`의 prompt |
