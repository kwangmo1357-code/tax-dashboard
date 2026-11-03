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

## TAX AI 챗봇 설정 (한 번만)

GitHub Pages는 화면만 보여주므로, 질문이 올 때마다 API 키로 Claude를 부르는 **서버 함수**(`worker/`)를 Cloudflare Workers(무료)에 둡니다.
코드는 이 저장소에서 관리하고, `worker/`를 고쳐 push하면 `.github/workflows/deploy-worker.yml`이 자동 배포합니다.

| 단계 | 어디서 | 할 일 |
|---|---|---|
| 1 | dash.cloudflare.com | 무료 가입 → 왼쪽 메뉴 **Workers & Pages** 한 번 열기 (workers.dev 하위 주소 이름 정하기) |
| 2 | Cloudflare 오른쪽 위 계정 → **My Profile → API Tokens** | **Create Token** → 템플릿 **Edit Cloudflare Workers** → 생성된 토큰 복사 |
| 3 | Cloudflare 첫 화면 오른쪽 | **Account ID** 복사 |
| 4 | 저장소 Settings → Secrets and variables → Actions → **Secrets** | `CLOUDFLARE_API_TOKEN`(2), `CLOUDFLARE_ACCOUNT_ID`(3), `TAX_AI_ACCESS_CODE`(팀원끼리 쓸 접속 코드, 직접 정함) 등록. `ANTHROPIC_API_KEY`·`LAW_OC`는 기존 것 그대로 사용 |
| 5 | 저장소 Actions 탭 | **TAX AI 챗봇 서버 배포** → Run workflow → 로그 끝의 `https://tax-ai.<이름>.workers.dev` 주소 복사 |
| 6 | 저장소 Settings → Secrets and variables → Actions → **Variables** | `TAX_AI_URL` = 5의 주소 |
| 7 | 저장소 Actions 탭 | **대시보드 데이터 갱신 및 배포** → Run workflow → 사이트 6번 섹션에서 접속 코드 입력 후 질문 |

| 바꾸고 싶은 것 | 위치 |
|---|---|
| 답변 모델·사고 깊이 | `worker/wrangler.toml` → `CHAT_MODEL`(기본 `claude-opus-5-5`), `CHAT_EFFORT` |
| 요청을 받을 사이트 주소 | `worker/wrangler.toml` → `ALLOWED_ORIGINS` |
| 답변 원칙·순서 | `worker/src/index.js` → `SYSTEM` |
| 질문 예시 | `site/index.html` → `AI_EXAMPLES` |

## 비용·보안 메모

| 항목 | 내용 |
|---|---|
| Claude 비용 | 첫 실행 때 약 100건 요약, 이후는 새 건만(보통 하루 0~10건). 기본 모델 `claude-haiku-4-5` 기준 월 몇백 원~몇천 원 수준 |
| API 키 | GitHub Secrets에만 저장되고, 공개 사이트와 `data.json`에는 들어가지 않음 |
| OC 값 | 링크를 만들 때 OC 값은 지움 |
| TAX AI 비용 | 질문 1건에 Claude 2~5회 호출(원문 검색 포함). Opus 5.5 기준 1건에 대략 100~500원(추정, 원문 길이에 따라 다름). 줄이려면 `CHAT_EFFORT`를 `medium`으로. Anthropic 콘솔 Limits에서 월 한도 필수 |
| TAX AI 보안 | 접속 코드가 맞고 `ALLOWED_ORIGINS` 주소에서 온 요청만 받음. 코드가 새면 `TAX_AI_ACCESS_CODE`를 바꾸고 서버 배포 다시 실행 |
| 공개 범위 | 무료 계정의 Pages는 공개 사이트. 회사 내부 정보(담당자·법인별 기한)는 넣지 말 것 |
| 휴일 | 주말과 고정 공휴일만 반영. 설·추석·대체공휴일은 `update_data.py`의 `HOLIDAYS_EXTRA`에 추가 |

## 수정 포인트

| 바꾸고 싶은 것 | 위치 |
|---|---|
| 추적 법령·관점 문구 | `update_data.py` → `LAW_FOCUS` |
| 검색어 / 주제 탭 분류 | `update_data.py` → `QUERIES` / `TOPIC_RULES` |
| 제외어 / 제조업 관련도 키워드 | `update_data.py` → `EXCLUDE` / `MFG_KEYS` |
| 영향 분석 카드 | `site/impact.json` → `items` (`basis`: 확인 / 확인 필요 / 분석) |
| XBRL 주석 작성 점검 | `site/xbrl.json` → `rules`(핵심 기준) / `groups[].items`(체크리스트, `id`는 바꾸지 말 것 — 체크 상태가 id로 저장됨, `page`는 가이드 본문 쪽수) |
| 화면만 다시 확인 (API 호출 없이 재분류) | `python scripts/update_data.py --offline` |
| 실행 시각 | `update.yml` → `cron` (UTC 기준, KST −9시간) |
| 요약 문구 스타일 | `update_data.py` → `claude_summarize()`의 prompt |
