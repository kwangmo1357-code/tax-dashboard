# 프로젝트: 회계·세무 대시보드 (정적 사이트)

이 폴더는 GitHub Pages로 배포하는 **파일 1개짜리 정적 대시보드**입니다.
Claude Code는 아래 맥락과 작업 지시를 따라 진행하세요.

## 구성
- `index.html` — 대시보드 본체. 외부 라이브러리·빌드 없음. 이 파일만 올리면 동작.
- `README.md` — 사람이 읽는 설명/수동 배포 안내.
- `CLAUDE.md` — (이 파일) Claude Code용 지시.

## 대시보드 내용
1. 세법 개정 레이더 — 주요 세법·외감법 공포일/시행일, 시행예정. 기본은 스냅샷(2026-10-28 기준), `index.html`의 `LAW_OC`에 법제처 OpenAPI 인증키를 넣으면 law.go.kr 실시간 호출 시도(실패 시 스냅샷 폴백).
2. 예규·판례 피드 — 국세청 해석 + 조세심판원 재결, 6개 주제 탭. 스냅샷.
3. 신고 마감 캘린더 — **샘플 데이터**(`index.html`의 `const SAMPLE`). 실제 기한으로 교체 필요.

## 배포 작업 (요청 시 수행)
GitHub CLI(`gh`)가 인증돼 있다고 가정. 저장소 이름은 사용자에게 확인하되 기본값 `tax-dashboard`.

```bash
cd "이 폴더"
git init -b main
git add index.html README.md
git commit -m "회계·세무 대시보드 초기 배포"
gh repo create tax-dashboard --public --source=. --remote=origin --push
# GitHub Pages 활성화 (main 브랜치 root)
gh api -X POST repos/{owner}/tax-dashboard/pages -f "source[branch]=main" -f "source[path]=/" || \
  gh api -X PUT repos/{owner}/tax-dashboard/pages -f "source[branch]=main" -f "source[path]=/"
```
배포 후 공개 주소: `https://<owner>.github.io/tax-dashboard/` (1~2분 지연). 사용자에게 주소를 알려줄 것.

## 갱신 작업
- 마감 캘린더: `index.html`의 `const SAMPLE = [ ['YYYY-MM-DD','항목','대상','담당','상태'], ... ]` 수정.
- 예규·판례: `const DEC = { '주제':[ {d,s,no,t,l}, ... ] }` 수정.
- 수정 후 `git add -A && git commit -m "..." && git push` 하면 사이트 자동 갱신.

## 주의
- 3번 캘린더는 실제 담당 건이 아닌 샘플. 공유 전 반드시 실제 기한으로 교체.
- `LAW_OC`에 키를 넣으면 **공개 저장소에 키가 노출**됨. 노출 원치 않으면 비워 둘 것.
- 스냅샷 날짜가 오래되면 `SNAPSHOT_DATE` 및 각 데이터 갱신 안내.
