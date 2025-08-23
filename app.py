# -*- coding: utf-8 -*-
# 블로그·유튜브 통합 생성기 — 최종 안정화본 (세션오류/무한로딩 패치 완료)

import os, re, json, time, uuid, inspect, html
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# ========================= 기본 설정 =========================
KST = timezone(timedelta(hours=9))
SAFE_BOOT    = True
CTA          = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

st.set_page_config(page_title="블로그·유튜브 통합 생성기", page_icon="⚡", layout="wide")
st.title("⚡ 블로그·유튜브 통합 생성기 (최종 안정화본)")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국어 고정 · EN 이미지 프롬프트 · 무한로딩 방지")

# 세션 기본값(읽기 안전 위해 기본값을 꼭 세팅)
st.session_state.setdefault("model_text", "gpt-4o-mini")
st.session_state.setdefault("_humanize_calls", 0)
st.session_state.setdefault("_humanize_used",  0.0)
st.session_state.setdefault("people_taste", True)

HUMANIZE_BUDGET_CALLS = 8
HUMANIZE_BUDGET_SECS  = 20.0

# components.html key 지원 확인
try:
    HTML_SUPPORTS_KEY = 'key' in inspect.signature(comp_html).parameters
except Exception:
    HTML_SUPPORTS_KEY = False

# ========================= API 키 자동 점검 =========================
def _load_api_key():
    return os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))

def _check_api_health():
    api_key = _load_api_key()
    if not api_key:
        st.error("❌ OpenAI API 키가 없습니다. Streamlit Secrets 또는 환경변수에 등록해 주세요.")
        st.stop()
    try:
        client = OpenAI(api_key=api_key, timeout=30)
        _ = client.models.list()   # 헬스체크
        st.success("✅ OpenAI API 연결 성공")
        return client
    except Exception as e:
        st.error("⚠️ OpenAI API 연결 실패 (키/프로젝트 권한/네트워크 확인)")
        st.exception(e)
        st.stop()

_ = _check_api_health()

# ========================= 복사 블록 =========================
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
        try:
            if HTML_SUPPORTS_KEY:
                comp_html(html_str, height=height+110, scrolling=False, key=f"copy_{uuid.uuid4().hex}")
            else:
                comp_html(html_str, height=height+110, scrolling=False)
        except TypeError:
            comp_html(html_str, height=height+110)
    else:
        st.markdown(f"**{title or ''}**")
        st.text_area("", text or "", height=height, key=f"ta_{uuid.uuid4().hex}")
        st.caption("복사: 영역 클릭 → Ctrl+A → Ctrl+C")

# ========================= OpenAI/LLM 헬퍼 =========================
def _client():
    ak = _load_api_key()
    if not ak:
        st.warning("🔐 OPENAI_API_KEY 없음", icon="⚠️"); st.stop()
    return OpenAI(api_key=ak, timeout=60)

def _extract_from_responses(r):
    txt = getattr(r, "output_text", None)
    if isinstance(txt, str) and txt.strip():
        return txt.strip()
    parts = []
    for item in getattr(r, "output", []) or []:
        for ct in getattr(item, "content", []) or []:
            if getattr(ct, "type", "") in ("output_text", "text"):
                t = getattr(ct, "text", "") or ""
                if t: parts.append(t)
    return "\n".join(parts).strip()

@st.cache_data(show_spinner=False)
def chat_cached(system, user, model, temperature):
    """무한대기 차단: 40초 하드 타임아웃 + responses 폴백"""
    REQUEST_DEADLINE = 40
    c = _client()

    def call_chat():
        return c.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=2200,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
        ).choices[0].message.content.strip()

    def call_responses_fallback():
        r = c.responses.create(
            model=model,
            input=[{"role":"system","content":system},{"role":"user","content":user}],
            max_output_tokens=2200,
            temperature=temperature,
        )
        return _extract_from_responses(r)

    def guarded_call():
        try: return call_chat()
        except Exception: return call_responses_fallback()

    waits = [0.0, 0.8]  # 2회 시도
    start = time.time()
    for w in waits:
        if w: time.sleep(w)
        remain = REQUEST_DEADLINE - (time.time() - start)
        if remain <= 0: break
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(guarded_call)
                return fut.result(timeout=max(5, remain))
        except (FuturesTimeout, Exception):
            continue

    # 완전 실패 시 안전 JSON 반환(렌더 강제)
    return json.dumps({
        "youtube": {
            "titles": [f"임시 제목 {i}" for i in range(1,11)],
            "description": "네트워크 지연으로 임시 설명입니다.",
            "chapters": [{"title":"임시 챕터","script":"임시 스크립트입니다."}],
            "images":{"thumbnail":{"en":"Korean context thumbnail, no text overlay"},
                      "chapters":[{"index":1,"en":"support visual, no text overlay"}]},
            "hashtags":["#임시","#생성","#보류"]*7
        },
        "blog": {
            "titles": [f"임시 블로그 제목 {i}" for i in range(1,11)],
            "body": "네트워크 지연으로 임시 본문입니다.\n\n[이미지:대표]",
            "images":[{"label":"대표","en":"Korean context, no text overlay"}],
            "tags":["#임시","#블로그","#태그"]*7
        }
    }, ensure_ascii=False)

def run_step_with_deadline(fn, deadline_sec=75, *a, **kw):
    with ThreadPoolExecutor(max_workers=1) as _ex:
        fut = _ex.submit(fn, *a, **kw)
        try:
            return fut.result(timeout=deadline_sec)
        except FuturesTimeout:
            raise TimeoutError(f"Step exceeded {deadline_sec}s")

# ========================= 유틸/보정 =========================
def safe_json_parse(raw, fallback):
    try: return json.loads(raw) if raw else fallback
    except Exception: return fallback

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
        ko = chat_cached("아래 목록을 자연스러운 한국어로 번역. 줄 수/순서 유지, 과장 금지.",
                         "\n".join(lines), model, 0.2)
        out = [ln.strip() for ln in ko.splitlines() if ln.strip()]
        return out[:len(lines)]
    return lines

def humanize_ko(text: str, mode: str, model: str, region: str = "관악구", persona: str = "강쌤") -> str:
    """세션 안전 접근(.get) + 예외 없는 업데이트"""
    if not text:
        return text

    # 안전 읽기 (스레드에서도 KeyError 방지)
    calls = st.session_state.get("_humanize_calls", 0)
    used  = st.session_state.get("_humanize_used", 0.0)

    start_ts = time.time()
    if (calls >= HUMANIZE_BUDGET_CALLS) or (used >= HUMANIZE_BUDGET_SECS):
        return text

    style_sys = (
        "당신은 한국어 글맛을 살리는 편집자입니다. 과장/광고톤 억제, 2~3문장마다 호흡, "
        f"지역({region})과 현장전문가 '{persona}'의 말투를 약하게 스며들게."
    )
    mode_line = "영업형: CTA는 마지막 1줄만." if mode == "sales" else "정보형: CTA 금지."
    ask = f"{mode_line}\n\n[원문]\n{text}\n\n원문 구조는 유지, 리듬과 어휘만 개선."

    out = chat_cached(style_sys, ask, model, 0.6)

    # 안전 업데이트
    try:
        st.session_state["_humanize_calls"] = calls + 1
        st.session_state["_humanize_used"]  = used + (time.time() - start_ts)
    except Exception:
        pass

    return out

# ========================= 타깃/이미지 프롬프트 =========================
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
    if re.search(r"(남성|남자|아빠|형|삼촌|신사|남편|중년남|아재)", t): gender = "남성"
    elif re.search(r"(여성|여자|엄마|언니|이모|숙녀|아내|중년여|여성전용)", t): gender = "여성"
    else: gender = "혼합"
    return age, gender

def build_kr_image_en(subject_en: str, age: str, gender: str, place: str, mood: str, shot: str, style: str) -> str:
    age_en = {"유아":"toddlers","아동":"children","청소년":"teenagers","20대":"people in their 20s",
              "30대":"people in their 30s","40대":"people in their 40s","50대":"people in their 50s",
              "60대":"people in their 60s","70대":"people in their 70s","성인":"adults"}.get(age,"adults")
    gender_en = {"남성":"Korean man","여성":"Korean woman","혼합":"Korean men and women"}.get(gender,"Korean men and women")
    place_en = {
        "한국 가정 거실":"modern Korean home living room interior",
        "한국 아파트 단지":"Korean apartment complex outdoor area",
        "한국 동네 공원":"local Korean neighborhood park",
        "한국 병원/검진센터":"Korean medical clinic or health screening center interior",
        "한국형 주방/식탁":"modern Korean kitchen and dining table"
    }.get(place,"modern Korean interior")
    shot_en  = {"클로즈업":"close-up","상반신":"medium shot","전신":"full body shot","탑뷰/테이블샷":"top view table shot"}.get(shot,"medium shot")
    mood_en  = {"따뜻한":"warm","밝은":"bright","차분한":"calm","활기찬":"energetic"}.get(mood,"warm")
    style_en = {"사진 실사":"realistic photography, high resolution","시네마틱":"cinematic photo style",
                "잡지 화보":"editorial magazine style","자연광":"natural lighting"}.get(style,"realistic photography, high resolution")
    return (f"{gender_en} {age_en} at a {place_en}, {shot_en}, {mood_en} mood, {style_en}. "
            f"Context: {subject_en}. natural lighting, high contrast, no text overlay, no captions, no watermarks, no logos.")

# ========================= 사이드바 =========================
with st.sidebar:
    st.header("⚙️ 생성 설정")
    st.selectbox("모델", ["gpt-4o-mini","gpt-4o"], index=0, key="model_text")
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
    people_taste = st.checkbox("사람맛 강화(2차 다듬기)", value=st.session_state.get("people_taste", True))
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

if SAFE_BOOT: st.caption("옵션 확인 후 아래 버튼으로 실행하세요.")
go = st.button("▶ 한 번에 생성", type="primary")

# 쓰레드 밖에서 모델값 고정(세션 직접 접근 금지)
MODEL = st.session_state.get("model_text", "gpt-4o-mini")

# ========================= LLM 스키마 =========================
def schema_for_llm(_:int):
    return f'''{{
  "demographics": {{
    "age_group": "{final_age}",
    "gender": "{final_gender}"
  }}
}}'''

# ========================= 생성 함수 =========================
def gen_youtube(topic, tone, n, mode, model):
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
    user = (f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n[N] {n}\n"
            f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(0)}")
    raw = chat_cached(sys, user, model, temperature)
    data = safe_json_parse(raw, {})
    yt = data.get("youtube") or {
        "titles":[f"{topic} 핵심 가이드 {i+1}" for i in range(10)],
        "description": f"{topic} 요약 가이드입니다.",
        "chapters":[{"title":f"Tip{i+1}","script":f"{topic} 핵심 포인트 {i+1}"} for i in range(n)],
        "images":{"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                  "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]},
        "hashtags":["#건강","#관리","#생활"]*5
    }

    yt["titles"] = ensure_korean_lines(yt.get("titles", [])[:10], model)
    desc = yt.get("description","")
    if _is_mostly_english(desc):
        yt["description"] = chat_cached("이 설명을 한국어로 자연스럽게 바꾸세요. 과장 없이 간결하게.", desc, model, 0.2)

    chs = []
    for c in yt.get("chapters", [])[:n]:
        sc = c.get("script","")
        if _is_mostly_english(sc):
            sc = chat_cached("아래 문단을 자연스러운 한국어로 바꾸세요.", sc, model, 0.2)
        chs.append({"title": c.get("title",""), "script": sc})
    yt["chapters"] = chs

    if mode=="sales":
        desc = (yt.get("description","") or "").rstrip()
        if CTA not in desc: yt["description"] = (desc + f"\n{CTA}").strip()

    if st.session_state.get("people_taste", True):
        yt["description"] = humanize_ko(yt.get("description",""), mode, model)
        for c in yt["chapters"]:
            c["script"] = humanize_ko(c.get("script",""), mode, model)
    return yt

def gen_blog(topic, tone, mode, min_chars, img_count, model):
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
    user = (f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n"
            f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(min_chars)}")
    raw = chat_cached(sys, user, model, temperature)
    data = safe_json_parse(raw, {})
    blog = data.get("blog") or {
        "titles":[f"{topic} 블로그 {i+1}" for i in range(10)],
        "body":f"{topic} 기본 안내",
        "images":[{"label":"대표","en":"Korean home context, no text overlay"}],
        "tags":["#건강","#식단","#생활","#관리"]*5
    }

    if len(blog.get("body","")) < min_chars:
        def _expand():
            return chat_cached(
                f"Expand to >={min_chars+300} Korean characters; keep structure & markers; RETURN JSON ONLY.",
                json.dumps({"blog":blog}, ensure_ascii=False),
                model, 0.5
            )
        try:
            ext = run_step_with_deadline(_expand, 35)
            blog = safe_json_parse(ext, {"blog":blog}).get("blog", blog)
        except Exception:
            pass

    if mode=="sales":
        if CTA not in blog.get("body",""):
            blog["body"] = blog.get("body","").rstrip() + f"\n\n{CTA}"
    else:
        blog["body"] = blog.get("body","").replace(CTA,"").strip()

    if st.session_state.get("people_taste", True):
        blog["body"] = humanize_ko(blog.get("body",""), mode, model)

    prompts = blog.get("images", [])[:img_count]
    while len(prompts) < img_count:
        i=len(prompts)
        prompts.append({"label":"대표" if i==0 else f"본문{i}",
                        "en":f"support visual for section {i} of '{topic}' (no text overlay)"})
    blog["images"] = prompts
    return blog

# ========================= 태그/내보내기 =========================
def _join_tags(tags, style: str) -> str:
    return "\n".join(tags) if style == "줄바꿈 여러 줄" else " ".join(tags)

def build_blog_body_with_tags(blog: dict, style: str) -> str:
    body = (blog.get("body") or "").rstrip()
    tags = _join_tags(blog.get("tags", []), style)
    return f"{body}\n\n{tags}".strip() if tags else body

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

# ========================= 실행 (순차 + 워치독) =========================
if go:
    try:
        st.session_state["people_taste"] = people_taste

        do_yt   = target in ["유튜브 + 블로그","유튜브만"]
        do_blog = target in ["유튜브 + 블로그","블로그만"]

        prog = st.progress(0); prog_text = st.empty()
        status = st.status("실행 로그", expanded=False); status.write("초기화…")
        results = {}

        # 유튜브
        if do_yt:
            prog.progress(15); prog_text.write("유튜브 패키지 생성 중…")
            status.write("유튜브 프롬프트 전송…")
            results["yt"] = run_step_with_deadline(gen_youtube, 75, topic, tone, target_chapter, mode, MODEL)
            status.write("유튜브 패키지 수신 완료")

        # 블로그
        if do_blog:
            prog.progress(45 if do_yt else 15); prog_text.write("블로그 패키지 생성 중…")
            status.write("블로그 프롬프트 전송…")
            results["blog"] = run_step_with_deadline(gen_blog, 90, topic, tone, mode, blog_min, blog_imgs, MODEL)
            status.write("블로그 패키지 수신 완료")

        # 렌더링
        prog.progress(85); prog_text.write("후처리 및 렌더링…"); status.write("후처리…")

        # ===== 유튜브 출력 =====
        if do_yt:
            st.markdown("## 📺 유튜브 패키지")
            yt = results.get("yt", {})
            st.markdown("**① 영상 제목(SEO 10)**")
            titles=[f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:10])]
            copy_block("영상 제목 복사", "\n".join(titles), 160, True)

            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", yt.get("description",""), 160, True)

            chapters = yt.get("chapters", [])[:target_chapter]
            full_vrew_script = "\n".join([c.get("script", "").replace("\n", " ") for c in chapters])
            st.markdown("**③ 브루 자막 — 전체 일괄 복사 (Vrew)**")
            copy_block("브루 자막 — 전체 일괄", full_vrew_script, 220, True)

            st.markdown("**④ 이미지 프롬프트 (EN only, no text overlay)**")
            if include_thumb:
                copy_block("[썸네일] EN",
                           build_kr_image_en(
                               f"YouTube thumbnail for topic: {topic}. Korean home context, healthy living.",
                               final_age, final_gender, img_place, img_mood, img_shot, img_style),
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
            blog = results.get("blog", {})
            st.markdown("**① 블로그 제목(SEO 10)**")
            bts=[f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:10])]
            copy_block("블로그 제목 복사", "\n".join(bts), 160, True)

            st.markdown("**② 본문 (강화 · 이미지 앵커 포함)**")
            copy_block("블로그 본문 복사", blog.get("body",""), 420, True)

            st.markdown("**②-β 본문 + 해시태그 (한 번에 복사)**")
            combined_text = build_blog_body_with_tags(blog, tag_join_style)
            copy_block("블로그 본문+해시태그", combined_text, 460, True)

            st.markdown("**③ 이미지 프롬프트 (EN only, no text overlay)**")
            if blog.get("images"):
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

        prog.progress(100); prog_text.write("완료")
        status.update(label="완료", state="complete")

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그를 확인해주세요.")
        st.exception(e)

st.markdown("---")
st.caption("무한로딩 방지(하드 타임아웃/폴백) · 세션 접근 안전화(.get) · 순차 실행 · 모델 인자 전달 · API 키 자동 점검")
