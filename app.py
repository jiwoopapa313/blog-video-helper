# -*- coding: utf-8 -*-
# 블로그·유튜브 통합 생성기 — 최종 안정본 (동기 실행 · 자동재시도 · 폴백 보강 · 무한로딩 차단)

import os, re, json, time, uuid, inspect, html
from datetime import datetime, timezone, timedelta
import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# ========================= 기본 설정 =========================
KST = timezone(timedelta(hours=9))
APP_TITLE = "⚡ 블로그·유튜브 통합 생성기 (최종 안정본)"
CTA = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

st.set_page_config(page_title="블로그·유튜브 통합 생성기", page_icon="⚡", layout="wide")
st.title(APP_TITLE)
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국어 고정 · EN 이미지 프롬프트 · 완전 동기 실행 · 무한로딩 차단")

# 세션 기본값(항상 setdefault 사용 → KeyError 방지)
st.session_state.setdefault("model_text", "gpt-4o-mini")
st.session_state.setdefault("_humanize_calls", 0)
st.session_state.setdefault("_humanize_used",  0.0)
st.session_state.setdefault("people_taste", False)  # 기본 OFF (안정성↑)

HUMANIZE_BUDGET_CALLS = 6
HUMANIZE_BUDGET_SECS  = 12.0

# components.html key 지원 확인
try:
    HTML_SUPPORTS_KEY = 'key' in inspect.signature(comp_html).parameters
except Exception:
    HTML_SUPPORTS_KEY = False

# ========================= API 키 및 클라이언트 =========================
def _load_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))

def _client() -> OpenAI:
    ak = _load_api_key()
    if not ak:
        st.error("❌ OPENAI_API_KEY가 없습니다. Streamlit Secrets 또는 환경변수에 등록해 주세요.")
        st.stop()
    # 요청 단위 타임아웃 (초) — 지연되면 즉시 예외 발생
    return OpenAI(api_key=ak, timeout=35)

# 부팅 시 1회 헬스체크 (실패 시 명확히 표시)
try:
    _ = OpenAI(api_key=_load_api_key(), timeout=10).models.list()
    st.success("✅ OpenAI API 연결 성공")
except Exception as e:
    st.error("⚠️ OpenAI API 연결 실패 — 키/프로젝트/네트워크 확인 필요")
    st.exception(e)
    st.stop()

# ========================= 공통 유틸 =========================
def _copy_iframe_html(title: str, esc_text: str, height: int) -> str:
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8" />
<style>
body{{margin:0;font-family:system-ui,-apple-system,'Noto Sans KR',Arial}}
.wrap{{border:1px solid #e5e7eb;border-radius:10px;padding:10px}}
.ttl{{font-weight:600;margin-bottom:6px}}
textarea{{width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;white-space:pre-wrap;box-sizing:border-box;font-family:ui-monospace,Menlo,Consolas}}
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

def safe_json_parse(raw, fallback):
    try:
        # 매우 드물게 마크업이 섞여오면 가장 바깥 { ... }만 추출
        if isinstance(raw, str):
            m = re.search(r"\{.*\}", raw, re.S)
            if m: raw = m.group(0)
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback

def _is_mostly_english(text: str) -> bool:
    if not text: return False
    letters = sum(ch.isalpha() for ch in text)
    if letters == 0: return False
    ascii_letters = sum(('a' <= ch.lower() <= 'z') for ch in text)
    return (ascii_letters / max(letters,1)) > 0.4

# ========================= LLM 호출(동기 · 자동 재시도 · 폴백) =========================
def safe_call_chat(system: str, user: str, model: str, temperature: float) -> str:
    """chat → 실패 시 responses 폴백, 3회 백오프 재시도, 최종 빈문자열 반환"""
    c = _client()
    waits = [0.6, 1.2, 2.0]
    for i, w in enumerate(waits):
        try:
            r = c.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=2100,
                timeout=35,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
            )
            return r.choices[0].message.content.strip()
        except Exception:
            # 폴백 - responses
            try:
                r = c.responses.create(
                    model=model,
                    input=[{"role":"system","content":system},{"role":"user","content":user}],
                    max_output_tokens=2100,
                    temperature=temperature,
                )
                if getattr(r, "output_text", None):
                    return r.output_text.strip()
                parts=[]
                for it in getattr(r, "output", []) or []:
                    for ct in getattr(it, "content", []) or []:
                        if getattr(ct, "type","") in ("text","output_text"):
                            t=getattr(ct, "text","")
                            if t: parts.append(t)
                if parts: return "\n".join(parts).strip()
            except Exception:
                pass
        if i < len(waits)-1:
            time.sleep(w)
    return ""  # 최종 실패

# ========================= 사람이 읽기 좋은 보정 =========================
def humanize_ko(text: str, mode: str, model: str, region: str = "관악구", persona: str = "강쌤") -> str:
    if not text: return text
    calls = st.session_state.get("_humanize_calls", 0)
    used  = st.session_state.get("_humanize_used", 0.0)
    start = time.time()
    if (calls >= HUMANIZE_BUDGET_CALLS) or (used >= HUMANIZE_BUDGET_SECS):
        return text
    style_sys = (
        "당신은 한국어 글맛을 살리는 편집자입니다. 과장/광고톤 억제, 2~3문장마다 호흡, "
        f"지역({region})과 현장전문가 '{persona}'의 말투를 약하게 스며들게."
    )
    mode_line = "영업형: CTA는 마지막 1줄만." if mode=="sales" else "정보형: CTA 금지."
    ask = f"{mode_line}\n\n[원문]\n{text}\n\n원문 구조는 유지, 리듬과 어휘만 개선."
    out = safe_call_chat(style_sys, ask, model, 0.5) or text
    st.session_state["_humanize_calls"] = calls + 1
    st.session_state["_humanize_used"]  = used + (time.time()-start)
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
    target_chapter = st.selectbox("유튜브 자막 개수", [5,6,7], 0)
    include_thumb  = st.checkbox("썸네일 프롬프트 포함", value=True)

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
    blog_min   = st.slider("최소 길이(자)", 1500, 4000, 1800, 100)  # 기본 1800자(안정)
    blog_imgs  = st.selectbox("이미지 프롬프트 수", [3,4,5,6], 2)
    tag_join_style = st.radio("블로그 태그 결합 방식", ["띄어쓰기 한 줄", "줄바꿈 여러 줄"], index=0)

    st.markdown("---")
    people_taste = st.checkbox("사람맛 강화(2차 다듬기)", value=st.session_state.get("people_taste", False))
    show_chapter_blocks = st.checkbox("자막 개별 복사 블록 표시", value=False)
    show_img_blocks     = st.checkbox("챕터/블로그 이미지 프롬프트 표시", value=False)

    st.markdown("---")
    if st.checkbox("강제 재생성(캐시 무시)", value=False):
        st.cache_data.clear()

# ========================= 입력 =========================
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

st.caption("옵션 확인 후 아래 버튼으로 실행하세요.")
go = st.button("▶ 한 번에 생성", type="primary")

MODEL = st.session_state.get("model_text", "gpt-4o-mini")

def schema_for_llm(_:int):
    return f'''{{
  "demographics": {{
    "age_group": "{final_age}",
    "gender": "{final_gender}"
  }}
}}'''

# ========================= 폴백(내용 보장) =========================
def fallback_youtube(topic: str, n: int):
    chaps = [{"title": f"{topic} 핵심 포인트 {i+1}",
              "script": f"{topic} 관련 핵심 포인트 {i+1}을(를) 현장 기준으로 간단히 설명합니다."}
             for i in range(n)]
    return {
        "titles": [f"{topic} 가이드 {i+1}" for i in range(10)],
        "description": f"{topic} 요약 가이드입니다. 사례와 체크포인트를 차분히 정리했습니다.",
        "chapters": chaps,
        "images": {"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                   "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]},
        "hashtags": ["#집수리","#현장팁","#강쌤철물"]*5
    }

def fallback_blog(topic: str, img_count: int, mode: str):
    body = (f"## {topic}\n\n"
            "네트워크 지연 또는 모델 응답 누락 시 제공되는 요약본입니다. 핵심만 빠르게 확인하세요.\n\n"
            "### 핵심 5가지\n"
            "1) 현장 진단\n2) 원인 추정\n3) 준비물 체크\n4) 작업 순서 진행\n5) 마무리 점검\n\n"
            "### 체크리스트(6~8)\n"
            "- 누수/결선/고정\n- 소음/진동\n- 경고등/오류코드\n- 마감 상태\n- 재방문 필요성\n- 사진 기록\n\n"
            "### 자가진단(5)\n- 증상 지속 여부\n- 특정 조건 민감도\n- 교체/수리 이력\n- 임시조치 효과\n- A/S 대상 여부\n\n"
            "### FAQ(3)\n- 시간: 1~3시간\n- 비용: 난이도/부품별 상이\n- 준비: 공간 확보·전원/밸브 차단\n\n"
            "[이미지:대표]\n[이미지:본문1]\n[이미지:본문2]\n")
    if mode=="sales": body += f"\n{CTA}"
    imgs = [{"label":"대표","en":"Korean home context, no text overlay"}] + \
           [{"label":f"본문{i}","en":f"support visual for section {i} of '{topic}' (no text overlay)"} for i in range(1, img_count)]
    return {"titles":[f"{topic} 블로그 {i+1}" for i in range(10)],
            "body":body, "images":imgs[:img_count],
            "tags":["#집수리","#시공후기","#관악구","#강쌤철물"]}

# ========================= 생성 함수(동기 1회 호출 + 보정) =========================
def gen_youtube(topic, tone, n, mode, model):
    sys = (
      "[persona / voice rules]\n"
      "- 화자: 20년 차 현장 전문가 ‘강쌤’. 차분+가벼운 유머. 존대.\n"
      "- 리듬: 짧/긴 문장 섞고 2~3문장마다 호흡.\n"
      "- 사례 1개 이상, 비교/주의/대안 포함. 마무리 2줄 요약+체크 3~5.\n\n"
      "You are a seasoned Korean YouTube scriptwriter. Return STRICT JSON ONLY.\n"
      "IMPORTANT: Titles/Description/Chapters in KOREAN. Image prompts in ENGLISH (no text overlay).\n"
      "Provide exactly N chapters (3~5 sentences each). Avoid clickbait."
    )
    user = (f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n[N] {n}\n"
            f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(0)}")
    raw = safe_call_chat(sys, user, model, min(temperature,0.6))
    data = safe_json_parse(raw, {})
    yt = data.get("youtube") or {}

    # 필수 필드 보정(제목만 왔을 때 자동 채움)
    if not yt.get("titles"): yt["titles"] = [f"{topic} 가이드 {i+1}" for i in range(10)]
    if (not yt.get("description")) or (not yt.get("chapters")):
        yt = fallback_youtube(topic, n)

    # 영어 섞인 설명/자막 한국어화
    if _is_mostly_english(yt.get("description","")):
        tr = safe_call_chat("이 설명을 자연스러운 한국어로 바꾸세요. 과장 없이 간결하게.", yt["description"], model, 0.2)
        yt["description"] = tr or yt["description"]

    chs=[]
    for i, c in enumerate(yt.get("chapters", [])[:n], 1):
        title = c.get("title") or f"{topic} 핵심 포인트 {i}"
        script = c.get("script") or f"{topic} 관련 핵심 포인트 {i}를 현장 기준으로 설명합니다."
        if _is_mostly_english(script):
            script = safe_call_chat("아래 문단을 자연스러운 한국어로 바꾸세요.", script, model, 0.2) or script
        chs.append({"title": title, "script": script})
    yt["chapters"] = chs

    if mode=="sales":
        desc = (yt.get("description","") or "").rstrip()
        if CTA not in desc: yt["description"] = (desc + f"\n{CTA}").strip()

    if st.session_state.get("people_taste", False):
        yt["description"] = humanize_ko(yt.get("description",""), mode, model)
        for c in yt["chapters"]:
            c["script"] = humanize_ko(c.get("script",""), mode, model)

    # 이미지 프롬프트 기본값
    if "images" not in yt:
        yt["images"] = {"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                        "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]}
    return yt

def gen_blog(topic, tone, mode, min_chars, img_count, model):
    sys = (
      "[persona / voice rules]\n"
      "- 화자: 20년 차 현장 전문가 ‘강쌤’. 차분+가벼운 유머. 존대.\n"
      "- 리듬: 짧/긴 문장 섞기, 2~3문장마다 호흡. 현장 디테일 1~2개.\n"
      "- 사례/비교/주의/대안 포함. 마무리 2줄 요약+체크 3~5.\n\n"
      "You are a Korean SEO writer for Naver blog. Return STRICT JSON ONLY.\n"
      f"Target length >= {min_chars} (짧아도 재호출 금지; 한 번에 작성).\n"
      "Structure: 서론 → 핵심5 → 체크리스트(6~8) → 자가진단(5) → FAQ(3) → 마무리.\n"
      "Info mode forbids CTA. Sales mode allows ONE CTA at the very last line.\n"
      "Provide 10 SEO titles, 20 tags, and EN image prompts with NO TEXT OVERLAY."
    )
    user = (f"[topic] {topic}\n[tone] {tone}\n[mode] {'info' if mode=='info' else 'sales'}\n"
            f"[demographics] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(min_chars)}")
    raw = safe_call_chat(sys, user, model, min(temperature,0.6))
    data = safe_json_parse(raw, {})
    blog = data.get("blog") or {}

    # 필수 필드 보정
    if (not blog.get("body")) or (len(blog.get("body","")) < 500):
        blog = fallback_blog(topic, img_count, mode)

    # CTA 처리
    if mode=="sales":
        if CTA not in blog.get("body",""):
            blog["body"] = (blog.get("body","").rstrip() + f"\n\n{CTA}")
    else:
        blog["body"] = (blog.get("body","") or "").replace(CTA,"").strip()

    # 사람맛 보정(예산 내)
    if st.session_state.get("people_taste", False):
        blog["body"] = humanize_ko(blog.get("body",""), mode, model)

    # 이미지 프롬프트 개수 맞추기
    prompts = (blog.get("images") or [])[:img_count]
    while len(prompts) < img_count:
        i = len(prompts)
        prompts.append({"label":"대표" if i==0 else f"본문{i}",
                        "en":f"support visual for section {i} of '{topic}' (no text overlay)"})
    blog["images"] = prompts

    # 제목/태그 기본값
    if not blog.get("titles"):
        blog["titles"] = [f"{topic} 블로그 {i+1}" for i in range(10)]
    if not blog.get("tags"):
        blog["tags"] = ["#집수리","#시공후기","#관악구","#강쌤철물"]

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
    chapters = "\n\n".join(f"[챕터 {i+1}] {c.get('title','')}\n{c.get('script','')}" for i,c in enumerate(yt.get('chapters',[])))
    desc = yt.get('description','').strip()
    tags = " ".join(yt.get('hashtags',[]))
    return f"# YouTube Package\n\n## Titles\n{titles}\n\n## Description\n{desc}\n\n## Chapters\n{chapters}\n\n## Hashtags\n{tags}\n"

def build_blog_md(blog: dict) -> str:
    titles = "\n".join(f"{i+1}. {t}" for i,t in enumerate(blog.get('titles',[])[:10]))
    body = blog.get('body','')
    tags = " ".join(blog.get('tags',[]))
    return f"# Blog Package\n\n## Titles\n{titles}\n\n## Body\n{body}\n\n## Tags\n{tags}\n"

# ========================= 실행(완전 동기) =========================
if go:
    try:
        st.session_state["people_taste"] = people_taste

        do_yt   = target in ["유튜브 + 블로그","유튜브만"]
        do_blog = target in ["유튜브 + 블로그","블로그만"]

        st.info("🔧 실행 중… (동기 처리)")

        results = {}

        if do_yt:
            st.write("📺 유튜브 생성 중…")
            results["yt"] = gen_youtube(topic, tone, target_chapter, mode, MODEL)

        if do_blog:
            st.write("📝 블로그 생성 중…")
            results["blog"] = gen_blog(topic, tone, mode, blog_min, blog_imgs, MODEL)

        st.success("✅ 생성 완료")

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
            if show_img_blocks and blog.get("images"):
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

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그를 확인해주세요.")
        st.exception(e)

st.markdown("---")
st.caption("완전 동기 실행 · 자동 재시도 · 본문/자막/설명 폴백 보장 · 세션 안전 접근(.get) · 캐시/스레드/워치독 제거")
