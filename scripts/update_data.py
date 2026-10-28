#!/usr/bin/env python3
"""회계·세무 대시보드 데이터 갱신 스크립트 (GitHub Actions에서 매일 실행).

1) 법제처 국가법령정보 Open API(DRF) — 세법 현행/시행예정, 국세청 해석례, 조세심판원 재결례
2) Claude API — 새로 나온 해석례·재결례만 요약 (이미 요약한 건은 data/summaries.json 캐시 재사용)
3) 법정 신고·납부 기한 자동 계산
결과: site/data.json  (GitHub Pages가 이 파일을 읽어 표를 그림)

환경변수
  LAW_OC            법제처 Open API 인증값(OC, 보통 가입 이메일의 @ 앞부분)  [필수]
  ANTHROPIC_API_KEY Claude 콘솔에서 발급한 API 키 (없으면 요약 생략)
  CLAUDE_MODEL      요약에 쓸 모델 (기본 claude-haiku-4-5)
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "site", "data.json")
CACHE_PATH = os.path.join(ROOT, "data", "summaries.json")

KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).date()

OC = os.environ.get("LAW_OC", "").strip()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-haiku-4-5"

LAWS = ["법인세법", "소득세법", "부가가치세법", "조세특례제한법",
        "국세기본법", "주식회사 등의 외부감사에 관한 법률"]
TOPICS = ["법인세", "부가가치세", "소득세", "감가상각", "접대비", "대손금"]
PER_SOURCE = 12      # 주제·출처별 조회 건수
FEED_LIMIT = 20      # 주제별 표시 건수
DRF = "https://www.law.go.kr/DRF"


# ---------------------------------------------------------------- 공통
def http_json(url, data=None, headers=None, timeout=30, retries=2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8")
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError("JSON이 아닌 응답 (OC 미신청 항목일 수 있음): " + url.split("?")[0])
        except Exception:
            if i == retries:
                raise
            time.sleep(2 * (i + 1))


def drf(path, **params):
    params = {"OC": OC, "type": "JSON", **params}
    return http_json(f"{DRF}/{path}?" + urllib.parse.urlencode(params))


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def ymd(s):
    """'20260701' / '2026.07.01' → '2026-07-01'"""
    d = re.sub(r"\D", "", str(s or ""))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else ""


def abs_link(link):
    if not link:
        return ""
    if link.startswith("http"):
        return link
    # 공개 페이지에 내 OC 값이 노출되지 않도록 제거
    link = re.sub(r"OC=[^&]*&?", "", link)
    return "https://www.law.go.kr" + link


# ---------------------------------------------------------------- 1. 세법 레이더
def fetch_laws():
    rows, errors = [], []
    min_pub = (TODAY - dt.timedelta(days=365 * 3)).strftime("%Y%m%d")
    for q in LAWS:
        try:
            cur = as_list(drf("lawSearch.do", target="law", query=q, display=10)
                          .get("LawSearch", {}).get("law"))
            pend = as_list(drf("lawSearch.do", target="eflaw", query=q, display=20, nw=2)
                           .get("LawSearch", {}).get("law"))
        except Exception as e:
            errors.append(f"{q}: {e}")
            rows.append({"name": q, "kind": "-", "pub": "", "eff": "", "status": "조회실패", "note": str(e)[:80]})
            continue
        for x, is_pending in [(c, False) for c in cur] + [(p, True) for p in pend]:
            name = x.get("법령명한글", "")
            if not name.startswith(q):
                continue
            if is_pending and str(x.get("공포일자", "")) < min_pub:
                continue   # 오래전 타법개정으로 걸린 먼 미래 시행분 제외
            eff = ymd(x.get("시행일자"))
            if is_pending and eff and eff <= TODAY.isoformat():
                continue   # 이미 시행된 건은 현행 목록에 있음
            rows.append({
                "name": name,
                "kind": x.get("법령구분명", ""),
                "rev": x.get("제개정구분명", ""),
                "pub": ymd(x.get("공포일자")),
                "eff": eff,
                "status": "시행예정" if (is_pending or (eff and eff > TODAY.isoformat())) else "현행",
                "link": abs_link(x.get("법령상세링크")),
            })
    seen, uniq = set(), []
    for r in rows:
        key = (r["name"], r["eff"], r["status"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    def order(r):   # 시행예정은 가까운 순, 현행은 최근 순
        n = int(r["eff"].replace("-", "") or 0)
        return (r["status"] != "시행예정", n if r["status"] == "시행예정" else -n)
    uniq.sort(key=order)
    return uniq, errors


# ---------------------------------------------------------------- 2. 해석례·재결례
def fetch_nts(topic):
    d = drf("lawSearch.do", target="ntsCgmExpc", query=topic, display=PER_SOURCE, sort="ddes")
    out = []
    for x in as_list(d.get("CgmExpc", {}).get("cgmExpc")):
        out.append({
            "id": "nts-" + str(x.get("법령해석일련번호", "")),
            "date": ymd(x.get("해석일자")),
            "src": "국세청 해석",
            "no": x.get("안건번호", ""),
            "title": x.get("안건명", ""),
            "link": abs_link(x.get("법령해석상세링크")),
            "gist": "",
        })
    return out


def fetch_tribunal(topic):
    d = drf("lawSearch.do", target="ttSpecialDecc", query=topic, display=PER_SOURCE, sort="ddes")
    out = []
    for x in as_list(d.get("Decc", {}).get("decc")):
        out.append({
            "id": "tt-" + str(x.get("특별행정심판재결례일련번호", "")),
            "date": ymd(x.get("의결일자")),
            "src": "조세심판원",
            "no": x.get("청구번호", ""),
            "title": x.get("사건명", ""),
            "link": abs_link(x.get("행정심판재결례상세링크")),
            "gist": "",
        })
    return out


def tribunal_gist(item_id):
    """재결요지(본문 일부) — 요약 품질을 높이기 위해 새 건만 조회"""
    try:
        d = drf("lawService.do", target="ttSpecialDecc", ID=item_id.replace("tt-", ""))
        s = d.get("SpecialDeccService", {})
        return (s.get("재결요지") or s.get("결정요지") or "")[:1200]
    except Exception:
        return ""


def fetch_feed():
    feed, errors = {}, []
    for t in TOPICS:
        rows = []
        for fn in (fetch_nts, fetch_tribunal):
            try:
                rows += fn(t)
            except Exception as e:
                errors.append(f"{t}/{fn.__name__}: {e}")
        rows.sort(key=lambda r: r["date"], reverse=True)
        feed[t] = rows[:FEED_LIMIT]
    return feed, errors


# ---------------------------------------------------------------- Claude 요약
def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def claude_summarize(items):
    """items: [{id, src, title, gist}] → {id: {"summary":..., "impact":...}}"""
    lines = []
    for it in items:
        body = f"요지: {it['gist']}" if it.get("gist") else ""
        lines.append(f"- id={it['id']} | {it['src']} | 제목: {it['title']} {body}")
    prompt = (
        "너는 한국 상장회사 회계팀의 세무 실무 보조다. 아래 국세청 해석례·조세심판원 재결례 각각에 대해\n"
        "summary: 쟁점과 결론을 한 문장(60자 이내)으로, 결론을 알 수 없으면 쟁점만\n"
        "impact: 법인 회계·세무 실무자가 확인할 점 한 문장(50자 이내)\n"
        "을 작성해. 제목·요지에 없는 사실은 지어내지 말고, 모르면 '원문 확인 필요'라고 써.\n"
        '출력은 JSON 객체 하나만: {"<id>": {"summary": "...", "impact": "..."}, ...}\n\n'
        + "\n".join(lines)
    )
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    res = http_json("https://api.anthropic.com/v1/messages", data=payload, timeout=120, headers={
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def add_summaries(feed):
    cache = load_cache()
    if not API_KEY:
        note = "ANTHROPIC_API_KEY 없음 — AI 요약 생략"
    else:
        note = ""
        new = {}
        for rows in feed.values():
            for r in rows:
                if r["id"] not in cache and r["id"] not in new:
                    new[r["id"]] = r
        todo = list(new.values())
        for it in todo:
            if it["id"].startswith("tt-"):
                it["gist"] = tribunal_gist(it["id"])
        for i in range(0, len(todo), 25):       # 25건씩 묶어서 호출 (비용 절감)
            batch = todo[i:i + 25]
            try:
                got = claude_summarize(batch)
                for it in batch:
                    if it["id"] in got:
                        cache[it["id"]] = {**got[it["id"]], "at": TODAY.isoformat(), "model": MODEL}
            except Exception as e:
                note = f"AI 요약 일부 실패: {e}"[:120]
        print(f"[claude] 새 요약 대상 {len(todo)}건, 캐시 {len(cache)}건")
    for rows in feed.values():
        for r in rows:
            c = cache.get(r["id"], {})
            r["summary"] = c.get("summary", "")
            r["impact"] = c.get("impact", "")
            r.pop("gist", None)
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
    return note


# ---------------------------------------------------------------- 3. 법정기한
# 주말·고정 공휴일만 반영 (설·추석·대체공휴일은 HOLIDAYS_EXTRA에 직접 추가)
FIXED_HOLIDAYS = {(1, 1), (3, 1), (5, 5), (6, 6), (8, 15), (10, 3), (10, 9), (12, 25)}
HOLIDAYS_EXTRA = {
    # 2026~2027 설·추석·대체공휴일 등 — 확정 공휴일을 확인해 추가하세요. 예: "2027-02-08",
}


def next_business_day(d):
    while d.weekday() >= 5 or (d.month, d.day) in FIXED_HOLIDAYS or d.isoformat() in HOLIDAYS_EXTRA:
        d += dt.timedelta(days=1)
    return d


def month_end(y, m):
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))


def deadlines(days_ahead=100):
    items = []
    end = TODAY + dt.timedelta(days=days_ahead)
    y, m = TODAY.year, TODAY.month
    for k in range(5):
        yy, mm = y + (m - 1 + k) // 12, (m - 1 + k) % 12 + 1
        pm = (mm - 2) % 12 + 1
        items.append((dt.date(yy, mm, 10), "원천세 신고·납부", f"{pm}월 지급분", "원천세"))
        items.append((month_end(yy, mm), "일용근로소득 지급명세서 제출", f"{pm}월 지급분", "지급명세서"))
        items.append((month_end(yy, mm), "간이지급명세서(사업소득) 제출", f"{pm}월 지급분", "지급명세서"))
    for yy in (y, y + 1):
        items += [
            (dt.date(yy, 1, 25), "부가가치세 확정신고·납부", "전년 2기", "부가세"),
            (dt.date(yy, 4, 25), "부가가치세 예정신고·납부", "1기 예정", "부가세"),
            (dt.date(yy, 7, 25), "부가가치세 확정신고·납부", "1기", "부가세"),
            (dt.date(yy, 10, 25), "부가가치세 예정신고·납부", "2기 예정", "부가세"),
            (dt.date(yy, 3, 10), "근로·퇴직소득 지급명세서 제출", "전년 귀속", "지급명세서"),
            (dt.date(yy, 3, 31), "법인세 신고·납부", "12월 결산법인", "법인세"),
            (dt.date(yy, 4, 30), "법인지방소득세 신고·납부", "12월 결산법인", "지방세"),
            (dt.date(yy, 8, 31), "법인세 중간예납", "12월 결산법인", "법인세"),
        ]
    out = []
    for d, name, target, cat in items:
        adj = next_business_day(d)
        if TODAY - dt.timedelta(days=7) <= adj <= end:
            out.append({"due": adj.isoformat(), "orig": d.isoformat(), "item": name,
                        "target": target, "cat": cat, "shifted": adj != d})
    out.sort(key=lambda r: r["due"])
    return out


# ---------------------------------------------------------------- main
def main():
    if not OC:
        sys.exit("LAW_OC 환경변수가 없습니다 (GitHub Secrets에 LAW_OC 등록 필요)")
    laws, e1 = fetch_laws()
    feed, e2 = fetch_feed()
    ai_note = add_summaries(feed)
    data = {
        "generatedAt": dt.datetime.now(KST).isoformat(timespec="minutes"),
        "today": TODAY.isoformat(),
        "model": MODEL if API_KEY else "",
        "aiNote": ai_note,
        "topics": TOPICS,
        "laws": laws,
        "feed": feed,
        "deadlines": deadlines(),
        "errors": e1 + e2,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    n = sum(len(v) for v in feed.values())
    print(f"[ok] 법령 {len(laws)}건 · 피드 {n}건 · 기한 {len(data['deadlines'])}건 · 오류 {len(data['errors'])}건")


if __name__ == "__main__":
    main()
