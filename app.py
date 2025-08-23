# -*- coding: utf-8 -*-
# app.py — 블로그·유튜브 통합 생성기 (완전체)
# 한국어 고정 · 이미지 EN only(no text) · 안정 모드 · 타임아웃/워치독 · 사람맛 강화 예산 ·
# 본문+해시태그 일괄 복사 · Vrew 일괄복사 · 이미지 앵커 · 진행률 표시

import os, re, json, time, uuid, inspect, html
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# ========================= 기본 설정 =========================
KST = timezone(timedelta(hours=9))
SAFE_BOOT    = True
MAX_WORKERS  = 2
CTA          = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

# 사람맛 보정 예산(패치 B)
HUMANIZE_BUDGET_CALLS = 8       # 한 세션 최대 호출수
HUMANIZE_BUDGET_SECS  = 20.0    # 누적 최대 초
st.session_state.setdefault("_humanize_calls", 0)
st.session_state.setdefault("_humanize_used",  0.0)

st.set_page_config(page_title="블로그·유튜브 통합 생성기", page_icon="⚡", layout="wide")
st.title("⚡ 블로그·유튜브 통합 생성기 (완전체)")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국어 고정 · 이미지 EN 전용(no text) · 안정 모드 · 무한로딩 방지")

# components.html key 지원 확인
try:
    HTML_SUPPORTS_KEY = 'key' in inspect.signature(comp_html).parameters
except Exception:
    HTML_SUPPORTS_KEY = False

# ========================= 복사 블록(iframe) =========================
def _copy_iframe_html(title: str, esc_text: str, height: int) -> str:
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8" />
<style>
body{{margin:0;font-family:system-ui,-apple-system,'Noto Sans KR',Arial}}
.wrap{{border:1px solid #e5e7eb;border-radius:10px;padding:10px}}
.ttl{{font-weight:600;margin-bottom:6px}}
textarea{{width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;
         white-space:pre-wrap;box-sizing:border-box;font-family:ui-monospace,Menlo,Consolas}}
.row{{display:flex;gap:8px;align-items:center;margin-top:8px}}
.btn{{padding:6px 10px;border-radius:8px;border:1px solid #d1d5db;cursor:pointer;background:#fff}}
small{{color:#6b7280}}
</style></head><body>
<div class="wrap">
  <div class="ttl">{html.escape(title or '')}</div>
  <textarea id="ta" readonly>{esc_text}</textarea>
  <div class="row">
    <button class="btn" id="copyBtn">📋 복사</button>
    <small>안 되면 텍스트 클릭 → Ctrl+A → Ctrl+C</small>
  </div>
</div>
<script>
(()=>{{const b=document.getElementById("copyBtn");const t=document.getElementById("ta");
if(!b||!t)return;b.onclick=async()=>{{try{{await navigator.clipboard.writeText(t.value);
b.textContent="✅ 복사됨";setTimeout(()=>b.textContent="📋 복사",1200)}}catch(e){{try{{t.focus();t.select();document.execCommand("copy");
b.textContent="✅ 복사됨";setTimeout(()=>b.textContent="📋 복사",1200)}}catch(err){{alert("복사가 차단되었습니다. 직접 선택해 복사해주세요.")}}}}}})();
</script></body></html>
"""

def copy_block(title: str, text: str, height: int = 160, use_button: bool = True):
    if use_button:
        esc_t = (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        html_str = _copy_iframe_html(title or "", esc_t, height)
        if HTML_SUPPORTS_KEY:
            comp_html(html_str, height=height+110, scrolling=False, key=f"copy_{uuid.uuid4().hex}")
        else:
            comp_html(html_str, height=height+110, scrolling=False)
    else:
        st.markdown(f"**{title or ''}**")
        st.text_area("", text or "", height=height, key=f"ta_{uuid.uuid4().hex}")
        st.caption("복사: 영역 클릭 → Ctrl+A → Ctrl+C")

# ========================= OpenAI + 재시도/타임아웃 =========================
def _client():
    ak = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not ak:
        st.warning("🔐 OPENAI_API_KEY가 없습니다. Streamlit Secrets 또는 환경변수에 설정해주세요.", icon="⚠️")
        st.stop()
    return OpenAI(api_key=ak)

def _retry(fn, *a, **kw):
    waits = [0.7, 1.2, 1.8]  # 패치 A: 총 3회, 짧게
    err = None
    for i, w in enumerate(waits):
        try:
            return fn(*a, **kw)
        except Exception as e:
            err = e
            if i < len(waits)-1: time.sleep(w)
    raise err

@st.cache_data(show_spinner=False)
def chat_cached(system, user, model, temperature):
    c = _client()
    def call():
        return c.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=2200,     # 패치 A: 무한응답 방지
            timeout=60,          # 패치 A: 60초 타임아웃
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":user},
            ],
        )
    r = _retry(call)
    return r.choices[0].message.content.strip()

# ========================= 워치독(패치 A) =========================
def run_step_with_deadline(fn, deadline_sec=75, *a, **kw):
    """fn(*a, **kw)를 deadline_sec 안에 끝내고, 넘기면 TimeoutError 던짐"""
    with ThreadPoolExecutor(max_workers=1) as _ex:
        fut = _ex.submit(fn, *a, **kw)
        try:
            return fut.result(timeout=deadline_sec)
        except FuturesTimeout:
            raise TimeoutError(f"Step exceeded {deadline_sec}s")

# ========================= JSON 세이프 파서(패치 C) =========================
def safe_json_parse(raw, fallback):
    try:
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback

# ========================= 한국어 보정 유틸 =========================
def _is_mostly_english(text: str) -> bool:
    if not text: return False
    letters = sum(ch.isalpha() for ch in text)
    if letters == 0: return False
    ascii_letters = sum(('a' <= ch.lower() <= 'z') for ch in text)
    return (ascii_letters / max(letters,1)) > 0.4

def ensure_korean_lines(lines, model):
    if not lines: return lines
    sample = " ".join(lines[:3])
    if _is_mostly_english(sample):
        ko = chat_cached(
            "아래 목록을 자연스러운 한국어로 번역하세요. 줄 수와 순서를 유지하고, 숫자/괄호/핵심 키워드는 살리되 과장표현은 피하세요.",
            "\n".join(lines),
            model, 0.2
        )
        out = [ln.strip() for ln in ko.splitlines() if ln.strip()]
        return out[:len(lines)]
    return lines

# 사람맛 보정(패치 B 예산)
def humanize_ko(text: str, mode: str, region: str = "관악구", persona: str = "강쌤") -> str:
    if not text: return text
    # 예산 체크
    start_ts = time.time()
    if (st.session_state["_humanize_calls"] >= HUMANIZE_BUDGET_CALLS) or (st.session_state["_humanize_used"] >= HUMANIZE_BUDGET_SECS):
        return text

    style_sys = (
        "당신은 한국어 글맛을 살리는 전문 편집자입니다. "
        "문장을 자연스럽고 생생하게 다듬되, 과장/감탄사/광고톤은 억제하세요. "
        "짧은 문장과 긴 문장을 섞고, 2~3문장마다 호흡을 둡니다. "
        f"지역 맥락({region})과 현장 전문가 '{persona}'의 말투를 약하게 스며들게 하세요. "
        "불필요한 반복을 줄이고, 핵심은 남겨 자연스러운 흐름으로 재배열하세요."
    )
    mode_line = "영업형: CTA는 마지막 1줄만, 그 외엔 정보 중심." if mode=="sales" else "정보형: CTA는 금지."
    ask = (
        f"{mode_line}\n\n[원문]\n{text}\n\n"
        "위 원문을 위 규칙에 맞춰 한국어로 자연스럽게 다듬어 주세요. "
        "문단은 유지하되, 리듬과 어휘만 개선하세요."
    )
    out = chat_cached(style_sys, ask, st.session_state.get("model_text","gpt-4o-mini"), 0.6)
    st.session_state["_humanize_calls"] += 1
    st.session_state["_humanize_used"]  += (time.time()-start_ts)
    return out

# ========================= 자동 타깃 추론 =========================
def detect_demo_from_topic(topic: str):
    t = (topic or "").lower()
    age = "성인"
    age_map = [
        (r"(유아|영유아|신생아)", "유아"),
        (r"(아동|초등|초등학생|키즈)", "아동"),
        (r"(청소년|중학생|고등학생|10대|틴|티네이저)", "청소년"),
        (r"(20대|2030)", "20대"),
        (r"(30대|3040)", "30대"),
        (r"(40대|4050)", "40대"),
        (r"(50대|장년|중년)", "50대"),
        (r"(60대|노년|시니어)", "60대"),
        (r"(70대|고령)", "70대"),
    ]
    for pat,label in age_map:
        if re.search(pat, t): age = label; break

    if re.search(r"(남성|남자|아빠|형|삼촌|신사|남편|중년남|아재)", t):
        gender = "남성"
    elif re.search(r"(여성|여자|엄마|언니|이모|숙녀|아내|중년여|여성전용)", t):
        gender = "여성"
    else:
        gender = "혼합"
    return age, gender

# ========================= 이미지 프롬프트 빌더(EN only) =========================
def build_kr_image_en(subject_en: str, age: str, gender: str, place: str, mood: str, shot: str, style: str) -> str:
    age_en = {
        "유아":"toddlers","아동":"children","청소년":"teenagers",
        "20대":"people in their 20s","30대":"people in their 30s","40대":"people in their 40s",
        "50대":"people in their 50s","60대":"people in their 60s","70대":"people in their 70s","성인":"adults"
    }.get(age, "adults")
    gender_en = {"남성":"Korean man","여성":"Korean woman","혼합":"Korean men and women"}.get(gender, "Korean men and women")
    place_en = {
        "한국 가정 거실":"modern Korean home living room interior",
        "한국 아파트 단지":"Korean apartment complex outdoor area",
        "한국 동네 공원":"local Korean neighborhood park",
        "한국 병원/검진센터":"Korean medical clinic or health screening center interior",
        "한국형 주방/식탁":"modern Korean kitchen and dining table"
    }.get(place, "modern Korean interior")
    shot_en  = {"클로즈업":"close-up","상반신":"medium shot","전신":"full body shot","탑뷰/테이블샷":"top view table shot"}.get(shot,"medium shot")
    mood_en  = {"따뜻한":"warm","밝은":"bright","차분한":"calm","활기찬":"energetic"}.get(mood,"warm")
    style_en = {"사진 실사":"realistic photography, high resolution","시네마틱":"cinematic photo style",
                "잡지 화보":"editorial magazine style","자연광":"natural lighting"}.get(style,"realistic photography, high resolution")

    return (f"{gender_en} {age_en} at a {place_en}, {shot_en}, {mood_en} mood, {style_en}. "
            f"Context: {subject_en}. natural lighting, high contrast, "
            f"no text overlay, no captions, no watermarks, no logos.")

# ========================= 사이드바 옵션 =========================
with st.sidebar:
    st.header("⚙️ 생성 설정")
    model_text   = st.selectbox("모델", ["gpt-4o-mini","gpt-4o"], 0)
    st.session_state["model_text"] = model_text
    temperature  = st.slider("창의성", 0.0, 1.2, 0.6, 0.1)

    st.markdown("---")
    safe_mode = st.checkbox("안정 모드(단일 요청)", value=True)
    include_thumb  = st.checkbox("썸네일 프롬프트 포함", value=True)
    target_chapter = st.selectbox("유튜브 자막 개수", [5,6,7], 0)

    st.markdown("---")
    st.markdown("### 🖼 한국인 고정 + 자동 연령/성별")
    img_age    = st.selectbox("연령", ["자동","유아","아동","청소년","20대","30대","40대","50대","60대","70대","성인"], 0)
    img_gender = st.selectbox("성별", ["자동","혼합","남성","여성"], 0)
    img_place  = st.selectbox("장소", ["한국 가정 거실","한국 아파트 단지","한국 동네 공원","한국 병원/검진센터","한국형 주방/식탁"], 0)
    img_mood   = st.selectbox("무드", ["따뜻한","밝은","차분한","활기찬"], 0)
    img_shot   = st.selectbox("샷", ["클로즈업","상반신","전신","탑뷰/테이블샷"], 1)
    img_style  = st.selectbox("스타일", ["사진 실사","시네마틱","잡지 화보","자연광"], 0)

    st.markdown("---")
    st.markdown("### 📝 블로그 강화")
    blog_min   = st.slider("최소 길이(자)", 1500, 4000, 2200, 100)
    blog_imgs  = st.selectbox("이미지 프롬프트 수", [3,4,5,6], 2)
    tag_join_style = st.radio("블로그 태그 결합 방식", ["띄어쓰기 한 줄", "줄바꿈 여러 줄"], index=0)

    st.markdown("---")
    people_taste = st.checkbox("사람맛 강화(2차 다듬기)", value=True)
    show_chapter_blocks = st.checkbox("자막 개별 복사 블록 표시", value=False)
    show_img_blocks     = st.checkbox("챕터/블로그 이미지 프롬프트 표시", value=False)

    st.markdown("---")
    if st.checkbox("강제 재생성(캐시 무시)", value=False):
        st.cache_data.clear()

# ========================= 입력 폼 =========================
st.subheader("🎯 주제 및 내용")
c1,c2,c3,c4 = st.columns([2,1,1,1])
with c1: topic = st.text_input("주제", value="50대 이후 조심해야 할 음식 TOP5")
with c2: tone  = st.selectbox("톤/스타일", ["시니어 친화형","전문가형","친근한 설명형"], 1)
with c3: mode_sel = st.selectbox("콘텐츠 유형", ["자동 분류","정보형(블로그 지수)","시공후기형(영업)"], 1)
with c4: target = st.selectbox("생성 대상", ["유튜브 + 블로그","유튜브만","블로그만"], 0)

def classify(txt):
    return "sales" if any(k in txt for k in ["시공","교체","설치","수리","누수","보수","후기","현장","관악","강쌤철물"]) else "info"
def ensure_mode():
    if mode_sel=="정보형(블로그 지수)": return "info"
    if mode_sel=="시공후기형(영업)":   return "sales"
    return classify(topic)
mode = ensure_mode()

auto_age, auto_gender = detect_demo_from_topic(topic)
final_age    = auto_age    if img_age    == "자동" else img_age
final_gender = auto_gender if img_gender == "자동" else img_gender

if SAFE_BOOT:
    st.caption("옵션 확인 후 아래 버튼으로 실행하세요.")
go = st.button("▶ 한 번에 생성", type="primary")

# ========================= LLM 스키마 요약 =========================
def schema_for_llm(blog_min_chars:int):
    return fr'''{{
  "demographics": {{"age_group": "{final_age}","gender": "{final_gender}"}},
  "youtube": {{
    "titles": ["...","...","...","...","...","...","...","...","...","..."],
    "description": "(한국어 3~6문장, 영업형은 마지막 1문장 CTA 허용)",
    "chapters": [{{"title":"챕터1","script":"..."}},{{"title":"챕터2","script":"..."}},{{"title":"챕터3","script":"..."}},{{"title":"챕터4","script":"..."}},{{"title":"챕터5","script":"..."}}],
    "images": {{
      "thumbnail": {{"en":"(EN only, no text overlay)"}},
      "chapters": [{{"index":1,"en":"(EN only, no text overlay)"}},{{"index":2,"en":"(EN only, no text overlay)"}},{{"index":3,"en":"(EN only, no text overlay)"}},{{"index":4,"en":"(EN only, no text overlay)"}},{{"index":5,"en":"(EN only, no text overlay)"}}]
    }},
    "hashtags": ["#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#.."]
  }},
  "blog": {{
    "titles": ["...","...","...","...","...","...","...","...","...","..."],
    "body": "서론→핵심5→체크리스트(6~8)→자가진단(5)→FAQ(3)→마무리, {blog_min_chars}+자, 본문 내 [이미지:대표/본문1/본문2/본문3/본문4] 3~5개 포함",
    "images": [{{"label":"대표","en":"(EN only, no text overlay)"}},{{"label":"본문1","en":"(EN only, no text overlay)"}},{{"label":"본문2","en":"(EN only, no text overlay)"}},{{"label":"본문3","en":"(EN only, no text overlay)"}},{{"label":"본문4","en":"(EN only, no text overlay)"}}],
    "tags": ["#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#.."]
  }}
}}'''

# ========================= 유튜브 생성(한국어 고정) =========================
def gen_youtube(topic, tone, n, mode):
    sys = (
      "[persona / voice rules]\n"
      "- 화자: 20년 차 현장 전문가 ‘강쌤’. 차분+가벼운 유머. 존대.\n"
      "- 리듬: 짧/긴 문장 섞고 2~3문장마다 호흡.\n"
      "- 사례 1개 이상, 비교/주의/대안 포함. 마무리 2줄 요약+체크 3~5.\n\n"
      "You are a seasoned Korean YouTube scriptwriter. Return STRICT JSON ONLY.\n"
      "IMPORTANT: 'titles', 'description', and 'chapters' MUST be written in KOREAN.\n"
      "Image prompts MUST be in ENGLISH ONLY and include 'no text overlay'.\n"
      "SEO titles (10, Korean) should include the main keyword early and avoid clickbait.\n"
      "Provide exactly N chapters (3~5 sentences each). All visuals in Korean context."
    )
    user = (
      f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n[N] {n}\n"
      f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(blog_min)}"
    )
    raw = chat_cached(sys, user, st.session_state["model_text"], temperature)
    data = safe_json_parse(raw, {})
    yt = data.get("youtube") or {
        "titles":[f"{topic} 핵심 가이드 {i+1}" for i in range(10)],
        "description": f"{topic} 요약 가이드입니다.",
        "chapters":[{"title":f"Tip{i+1}","script":f"{topic} 핵심 포인트 {i+1}"} for i in range(n)],
        "images":{"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                  "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]},
        "hashtags":["#건강","#관리","#생활"]*5
    }

    # 한국어 보정
    yt["titles"] = ensure_korean_lines(yt.get("titles", [])[:10], st.session_state["model_text"])
    desc = yt.get("description","")
    if _is_mostly_english(desc):
        yt["description"] = chat_cached("이 설명을 한국어로 자연스럽게 바꾸세요. 과장 없이 간결하게.", desc, st.session_state["model_text"], 0.2)

    chs = []
    for c in yt.get("chapters", [])[:n]:
        sc = c.get("script","")
        if _is_mostly_english(sc):
            sc = chat_cached("아래 문단을 자연스러운 한국어로 바꾸세요.", sc, st.session_state["model_text"], 0.2)
        chs.append({"title": c.get("title",""), "script": sc})
    yt["chapters"] = chs

    if mode=="sales":
        desc = (yt.get("description","") or "").rstrip()
        if CTA not in desc: yt["description"] = (desc + f"\n{CTA}").strip()

    # 사람맛 강화(예산 내)
    if st.session_state.get("people_taste", True):
        yt["description"] = humanize_ko(yt.get("description",""), mode)
        for c in yt["chapters"]:
            c["script"] = humanize_ko(c.get("script",""), mode)

    return yt

# ========================= 블로그 생성 =========================
def gen_blog(topic, tone, mode, min_chars, img_count):
    sys = (
      "[persona / voice rules]\n"
      "- 화자: 20년 차 현장 전문가 ‘강쌤’. 차분+가벼운 유머. 존대.\n"
      "- 리듬: 짧/긴 문장 섞기, 2~3문장마다 호흡. 현장 디테일 1~2개.\n"
      "- 사례/비교/주의/대안 포함. 마무리 2줄 요약+체크 3~5.\n\n"
      "You are a Korean SEO writer for Naver blog. Return STRICT JSON ONLY.\n"
      f"Body MUST be >= {min_chars} Korean characters and include 3~5 '[이미지:대표/본문1/본문2/본문3/본문4]' markers.\n"
      "Structure: 서론 → 핵심5 → 체크리스트(6~8) → 자가진단(5) → FAQ(3) → 마무리.\n"
      "Info mode forbids CTA. Sales mode allows ONE CTA at the very last line.\n"
      "Provide 10 SEO titles, 20 tags, and EN image prompts with NO TEXT OVERLAY."
    )
    user = (
      f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n"
      f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(min_chars)}"
    )
    raw = chat_cached(sys, user, st.session_state["model_text"], temperature)
    data = safe_json_parse(raw, {})
    blog = data.get("blog") or {
        "titles":[f"{topic} 블로그 {i+1}" for i in range(10)],
        "body":f"{topic} 기본 안내",
        "images":[{"label":"대표","en":"Korean home context, no text overlay"}],
        "tags":["#건강","#식단","#생활","#관리"]*5
    }

    # 패치 D: 최소 길이 보강 + 워치독
    if len(blog.get("body","")) < min_chars:
        def _expand():
            return chat_cached(
                f"Expand to >={min_chars+300} Korean characters; keep structure & markers; RETURN JSON ONLY.",
                json.dumps({"blog":blog}, ensure_ascii=False),
                st.session_state["model_text"], 0.5
            )
        try:
            ext = run_step_with_deadline(_expand, 35)  # 35초 상한
            blog = safe_json_parse(ext, {"blog":blog}).get("blog", blog)
        except Exception:
            pass

    # CTA 처리
    if mode=="sales":
        if CTA not in blog.get("body",""):
            blog["body"] = blog.get("body","").rstrip() + f"\n\n{CTA}"
    else:
        blog["body"] = blog.get("body","").replace(CTA,"").strip()

    # 사람맛 강화(예산 내)
    if st.session_state.get("people_taste", True):
        blog["body"] = humanize_ko(blog.get("body",""), mode)

    # 이미지 프롬프트 개수 정리
    prompts = blog.get("images", [])[:img_count]
    while len(prompts) < img_count:
        i=len(prompts)
        prompts.append({"label":"대표" if i==0 else f"본문{i}",
                        "en":f"support visual for section {i} of '{topic}' (no text overlay)"})
    blog["images"] = prompts
    return blog

# ========================= 태그 결합/본문+태그 헬퍼 =========================
def _join_tags(tags, style: str) -> str:
    tags = tags or []
    if style == "줄바꿈 여러 줄":
        return "\n".join(tags)
    return " ".join(tags)  # 기본: 한 줄

def build_blog_body_with_tags(blog: dict, style: str) -> str:
    body = (blog.get("body") or "").rstrip()
    tag_str = _join_tags(blog.get("tags", []), style)
    if not tag_str:
        return body
    return f"{body}\n\n{tag_str}".strip()

# ========================= 내보내기 포맷 =========================
def build_youtube_txt(yt: dict) -> str:
    titles = "\n".join(f"{i+1}. {t}" for i,t in enumerate(yt.get('titles',[])[:10]))
    chapters = "\n\n".join(f"[챕터 {i+1}] {c.get('title','')}\n{c.get('script','')}"
                           for i,c in enumerate(yt.get('chapters',[])))
    desc = yt.get('description','').strip()
    tags = " ".join(yt.get('hashtags',[]))
    return f"# YouTube Package\n\n## Titles\n{titles}\n\n## Description\n{desc}\n\n## Chapters\n{chapters}\n\n## Hashtags\n{tags}\n"

def build_blog_md(blog: dict) -> str:
    titles = "\n".join(f"{i+1}. {t}" for i,t in enumerate(blog.get('titles',[])[:10]))
    body = blog.get('body','')
    tags = " ".join(blog.get('tags',[]))
    return f"# Blog Package\n\n## Titles\n{titles}\n\n## Body\n{body}\n\n## Tags\n{tags}\n"

# ========================= 실행(패치 E: 진행률 표시) =========================
if go:
    try:
        # 옵션 공유
        st.session_state["people_taste"] = people_taste

        do_yt   = target in ["유튜브 + 블로그","유튜브만"]
        do_blog = target in ["유튜브 + 블로그","블로그만"]

        prog = st.progress(0, text="준비 중…")
        results={}

        # 실행(안정 모드 시 단일 스레드)
        with ThreadPoolExecutor(max_workers=1 if safe_mode else MAX_WORKERS) as ex:
            futs=[]
            if do_yt:
                prog.progress(15, text="유튜브 패키지 생성 중…")
                futs.append(("yt", ex.submit(run_step_with_deadline, gen_youtube, 75, topic, tone, target_chapter, mode)))
            if do_blog:
                prog.progress(45 if do_yt else 15, text="블로그 패키지 생성 중…")
                futs.append(("blog", ex.submit(run_step_with_deadline, gen_blog, 90, topic, tone, mode, blog_min, blog_imgs)))
            for name,f in futs:
                results[name]=f.result()

        prog.progress(85, text="후처리 및 렌더링…")

        # ===== 유튜브 출력 =====
        if do_yt:
            st.markdown("## 📺 유튜브 패키지")
            yt=results.get("yt",{})

            st.markdown("**① 영상 제목(SEO 10)**")
            titles=[f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:10])]
            copy_block("영상 제목 복사", "\n".join(titles), 160, True)

            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", yt.get("description",""), 160, True)

            chapters = yt.get("chapters", [])[:target_chapter]
            full_vrew_script = "\n".join([c.get("script", "").replace("\n", " ") for c in chapters])
            st.markdown("**③ 브루 자막 — 전체 일괄 복사 (Vrew)**")
            copy_block("브루 자막 — 전체 일괄", full_vrew_script, 220, True)

            if show_chapter_blocks:
                exp = st.expander("챕터별 자막 복사 (펼쳐서 보기)", expanded=False)
                with exp:
                    for i,c in enumerate(chapters,1):
                        copy_block(f"[챕터 {i}] {c.get('title',f'챕터 {i}')}", c.get("script",""), 140, True)

            st.markdown("**④ 이미지 프롬프트 (EN only, no text overlay)**")
            if include_thumb:
                copy_block("[썸네일] EN",
                           build_kr_image_en(
                               f"YouTube thumbnail for topic: {topic}. Korean home context, healthy living.",
                               final_age, final_gender, img_place, img_mood, img_shot, img_style),
                           110, True)

            if show_img_blocks:
                ips=(yt.get("images",{}) or {}).get("chapters",[])
                if len(ips)<len(chapters):
                    for i in range(len(ips),len(chapters)):
                        ips.append({"index":i+1,"en":"support visual, no text overlay"})
                expi=st.expander("챕터별 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                with expi:
                    for i,p in enumerate(ips[:target_chapter],1):
                        base = p.get("en","") or f"support visual for chapter {i} about '{chapters[i-1].get('title','')}'"
                        copy_block(f"[챕터 {i}] EN",
                                   build_kr_image_en(base, final_age, final_gender, img_place, img_mood, img_shot, img_style),
                                   110, True)

            st.markdown("**⑤ 해시태그(20)**")
            copy_block("해시태그 복사", " ".join(yt.get("hashtags",[])), 90, True)

            st.download_button("⬇️ 유튜브 패키지 .txt 저장",
                               build_youtube_txt(yt).encode("utf-8"),
                               file_name="youtube_package.txt", mime="text/plain",
                               key=f"dl_yt_{uuid.uuid4().hex}")

        # ===== 블로그 출력 =====
        if do_blog:
            st.markdown("---"); st.markdown("## 📝 블로그 패키지")
            blog=results.get("blog",{})

            st.markdown("**① 블로그 제목(SEO 10)**")
            bts=[f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:10])]
            copy_block("블로그 제목 복사", "\n".join(bts), 160, True)

            st.markdown("**② 본문 (강화 · 이미지 앵커 포함)**")
            copy_block("블로그 본문 복사", blog.get("body",""), 420, True)

            # 본문 + 해시태그 한 번에
            st.markdown("**②-β 본문 + 해시태그 (한 번에 복사)**")
            combined_text = build_blog_body_with_tags(blog, tag_join_style)
            copy_block("블로그 본문+해시태그", combined_text, 460, True)

            st.markdown("**③ 이미지 프롬프트 (EN only, no text overlay)**")
            if show_img_blocks:
                expb = st.expander("블로그 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                with expb:
                    for p in blog.get("images",[]):
                        base = p.get("en","") or f"support visual for section '{p.get('label','')}'"
                        copy_block(f"[{p.get('label','이미지')}] EN",
                                   build_kr_image_en(base, final_age, final_gender, img_place, img_mood, img_shot, img_style),
                                   110, True)

            st.markdown("**④ 태그(20)**")
            copy_block("블로그 태그 복사", _join_tags(blog.get("tags",[]), tag_join_style), 100, True)

            st.download_button("⬇️ 블로그 패키지 .md 저장",
                               build_blog_md(blog).encode("utf-8"),
                               file_name="blog_package.md", mime="text/markdown",
                               key=f"dl_blog_{uuid.uuid4().hex}")

        prog.progress(100, text="완료")

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그를 확인해주세요.")
        st.exception(e)

st.markdown("---")
st.caption("무한로딩 방지(타임아웃/워치독/폴백) · 안정 모드 · 사람맛 강화 예산 · EN 이미지 프롬프트 · 본문+해시태그 일괄복사")
