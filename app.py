# -*- coding: utf-8 -*-
# app.py — 통합본 (한국인 고정 + 자동 연령/성별 + Vrew 일괄복사 + 복사버튼 호환 + 내보내기)
import os, re, json, time, uuid, inspect, html
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# ====== 전역 설정 ======
KST = timezone(timedelta(hours=9))
SAFE_BOOT    = True        # UI 먼저 띄우고 버튼 클릭 시 실행
USE_COPY_BTN = True        # 복사 버튼 사용 (문제 시 사이드바에서 수동 복사로 전환)
MAX_WORKERS  = 2
DEBUG_PING   = True
CTA          = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

st.set_page_config(page_title="블로그·유튜브 통합 생성기", page_icon="⚡", layout="wide")
st.title("⚡ 블로그·유튜브 통합 생성기 (최신 통합본)")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국인 고정 · 자동 연령/성별 · 병렬 생성 · 복사/내보내기")

if DEBUG_PING: st.write("✅ READY")
if SAFE_BOOT:  st.info("세이프 부팅: 옵션 설정 후 **[▶ 한 번에 생성]** 버튼으로 실행합니다.")

# ====== html(key) 지원 확인 (환경별 호환) ======
try:
    HTML_SUPPORTS_KEY = 'key' in inspect.signature(comp_html).parameters
except Exception:
    HTML_SUPPORTS_KEY = False

# ====== 유틸: 복사 블록 ======
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
    use_button = use_button and USE_COPY_BTN
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

# ====== OpenAI 클라이언트/호출 ======
def _client():
    ak = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not ak:
        st.warning("🔐 OPENAI_API_KEY가 없습니다. Streamlit Secrets 또는 환경변수에 설정해주세요.", icon="⚠️")
        return None
    return OpenAI(api_key=ak)

def _retry(fn, *a, **kw):
    waits=[0.7,1.2,2.0,3.0]
    err=None
    for i,w in enumerate(waits):
        try: return fn(*a, **kw)
        except Exception as e:
            err=e
            if i < len(waits)-1: time.sleep(w)
    raise err

@st.cache_data(show_spinner=False)
def chat_cached(system, user, model, temperature):
    c = _client()
    if not c: return "{}"
    def call():
        return c.chat.completions.create(
            model=model, temperature=temperature,
            messages=[{"role":"system","content":system},{"role":"user","content":user}]
        )
    r = _retry(call)
    return r.choices[0].message.content.strip()

def json_complete(system, user, model, temperature, fallback: dict):
    raw = chat_cached(system, user, model, temperature)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) and data else fallback
    except Exception:
        raw2 = chat_cached(system+" RETURN JSON ONLY.", user, model, 0.3)
        try:
            data2 = json.loads(raw2)
            return data2 if isinstance(data2, dict) and data2 else fallback
        except Exception:
            return fallback

# ====== (NEW) 주제 기반 자동 연령/성별 추론 ======
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

# ====== 이미지 프롬프트 빌더 (한국인 고정) ======
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
    return (f"Korean ethnicity visible; {gender_en} {age_en} at a {place_en}, {shot_en}, {mood_en} mood, {style_en}. "
            f"Context: {subject_en}. Asian facial features; subtle Korean signage/items; avoid Western features; high contrast.")

# ====== 사이드바 옵션 ======
with st.sidebar:
    st.header("⚙️ 생성 설정")
    model_text   = st.selectbox("모델", ["gpt-4o-mini","gpt-4o"], 0)
    temperature  = st.slider("창의성", 0.0, 1.2, 0.6, 0.1)
    polish       = st.checkbox("후가공(4o로 문장 다듬기)", value=False)

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
    blog_min   = st.slider("최소 길이(자)", 1500, 4000, 2200, 100)
    blog_imgs  = st.selectbox("이미지 프롬프트 수", [3,4,5,6], 2)

    st.markdown("---")
    st.markdown("### 🧩 화면 부하 줄이기")
    show_chapter_blocks = st.checkbox("자막 개별 복사 블록 표시", value=False)
    show_img_blocks     = st.checkbox("챕터/블로그 이미지 프롬프트 표시", value=False)
    use_copy_button     = st.radio("복사 방식", ["복사 버튼","세이프(수동 복사)"], 0) == "복사 버튼"

    st.markdown("---")
    force_refresh = st.checkbox("강제 재생성(캐시 무시)", value=False)
    if force_refresh: st.cache_data.clear()

# ====== 입력 폼 ======
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

# (NEW) 자동 연령/성별 → 최종 값 확정
auto_age, auto_gender = detect_demo_from_topic(topic)
final_age    = auto_age    if img_age    == "자동" else img_age
final_gender = auto_gender if img_gender == "자동" else img_gender

if SAFE_BOOT:
    st.caption("세팅 확인 → 아래 버튼으로 생성")
go = st.button("▶ 한 번에 생성", type="primary")

# ====== LLM 스키마 ======
def schema_for_llm(blog_min_chars:int):
    return fr'''{{
  "demographics": {{
    "age_group": "{final_age}",
    "gender": "{final_gender}"
  }},
  "youtube": {{
    "titles": ["...","...","...","...","...","...","...","...","...","..."],
    "description": "(정보형 4~6문장 / 영업형은 마지막 1문장 CTA 허용)",
    "chapters": [{{"title":"챕터1","script":"..."}},{{"title":"챕터2","script":"..."}},{{"title":"챕터3","script":"..."}},{{"title":"챕터4","script":"..."}},{{"title":"챕터5","script":"..."}}],
    "images": {{
      "thumbnail": {{"en":"...","ko":"..."}},
      "chapters": [{{"index":1,"en":"...","ko":"..."}},{{"index":2,"en":"...","ko":"..."}},{{"index":3,"en":"...","ko":"..."}},{{"index":4,"en":"...","ko":"..."}},{{"index":5,"en":"...","ko":"..."}}]
    }},
    "hashtags": ["#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#.."]
  }},
  "blog": {{
    "titles": ["...","...","...","...","...","...","...","...","...","..."],
    "body": "서론→핵심5→체크리스트(6~8)→자가진단(5)→FAQ(3)→마무리, {blog_min_chars}+자, 본문 내 [이미지:설명] 3~5개 포함",
    "images": [{{"label":"대표","en":"...","ko":"..."}},{{"label":"본문1","en":"...","ko":"..."}},{{"label":"본문2","en":"...","ko":"..."}},{{"label":"본문3","en":"...","ko":"..."}},{{"label":"본문4","en":"...","ko":"..."}}],
    "tags": ["#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#..","#.."]
  }}
}}'''

# ====== 생성 로직 (유튜브) ======
def gen_youtube(topic, tone, n, mode):
    sys = (
      "You are a seasoned Korean YouTube scriptwriter for various age/gender audiences.\n"
      "All images must depict KOREAN ethnicity (avoid Western features) and include subtle Korean context.\n"
      "Return STRICT JSON ONLY matching the schema. Provide exactly N chapters (3~5 sentences each),\n"
      "and provide thumbnail + 1:1 chapter image prompts (EN/KO). SEO titles (10) should include\n"
      "main keyword in first 20 chars, optional numbers/brackets, and avoid clickbait. Hashtags 20."
    )
    user = (
      f"[topic] {topic}\n"
      f"[tone] {tone}\n"
      f"[mode] {'info' if mode=='info' else 'sales'}\n"
      f"[N] {n}\n"
      f"[demographics] age={final_age}, gender={final_gender} (FIXED)\n"
      f"[schema]\n{schema_for_llm(blog_min)}"
    )
    fallback = {
        "youtube":{
            "titles":[f"{topic} 가이드 {i+1}" for i in range(10)],
            "description":f"{topic} 설명(폴백).",
            "chapters":[{"title":f"Tip{i+1}","script":f"{topic} 핵심 팁 {i+1} (폴백)"} for i in range(n)],
            "images":{"thumbnail":{"en":"fallback thumb","ko":"폴백 썸네일"},
                      "chapters":[{"index":i+1,"en":"fallback","ko":"폴백"} for i in range(n)]},
            "hashtags":["#폴백"]*20
        },
        "blog":{"titles":[f"{topic} 블로그 {i+1}" for i in range(10)],"body":f"{topic} 폴백 본문",
                "images":[{"label":"대표","en":"fallback","ko":"폴백"}],"tags":["#폴백"]*20},
        "demographics":{"age_group":final_age,"gender":final_gender}
    }
    data = json_complete(sys, user, model_text, temperature, fallback)
    yt = data.get("youtube", fallback["youtube"])
    # 영업형이면 설명 마지막 줄에 CTA 삽입
    if mode=="sales":
        desc = (yt.get("description","") or "").rstrip()
        if CTA not in desc: yt["description"] = (desc + f"\n{CTA}").strip()
    return yt

# ====== 생성 로직 (블로그) ======
def gen_blog(topic, tone, mode, min_chars, img_count):
    sys = (
      "You are a Korean SEO writer for Naver blog. Return STRICT JSON ONLY.\n"
      f"Body MUST be >= {min_chars} Korean characters and include 3~5 '[이미지: ...]' markers.\n"
      "Structure: 서론 → 핵심5 → 체크리스트(6~8) → 자가진단(5) → FAQ(3) → 마무리.\n"
      "Info mode forbids CTA. Sales mode allows ONE CTA at the very last line.\n"
      "Provide 10 SEO titles, 20 tags, and 5 image prompts (대표+본문1~4) with EN/KO."
    )
    user = (
      f"[topic] {topic}\n"
      f"[tone] {tone}\n"
      f"[mode] {'info' if mode=='info' else 'sales'}\n"
      f"[demographics] age={final_age}, gender={final_gender} (FIXED)\n"
      f"[schema]\n{schema_for_llm(min_chars)}"
    )
    fallback = {
        "titles":[f"{topic} 블로그 {i+1}" for i in range(10)],
        "body":f"{topic} 폴백 본문",
        "images":[{"label":"대표","en":"fallback","ko":"폴백"}]+[
            {"label":f"본문{i}","en":"fallback","ko":"폴백"} for i in range(1,4)
        ],
        "tags":["#폴백"]*20
    }
    data = json_complete(sys, user, model_text, temperature, {"blog":fallback})
    blog = data.get("blog", fallback)
    # 길이 보정
    if len(blog.get("body","")) < min_chars:
        try:
            blog = json.loads(chat_cached(
                f"Expand to >={min_chars+300} Korean characters; keep structure & markers; RETURN JSON ONLY.",
                json.dumps({"blog":blog}, ensure_ascii=False),
                model_text, 0.5
            ))["blog"]
        except Exception: pass
    # CTA 처리
    if mode=="sales":
        if CTA not in blog.get("body",""):
            blog["body"] = blog.get("body","").rstrip() + f"\n\n{CTA}"
    else:
        blog["body"] = blog.get("body","").replace(CTA,"").strip()
    # 이미지 수 보정
    prompts = blog.get("images", [])[:img_count]
    while len(prompts) < img_count:
        i=len(prompts)
        prompts.append({"label":"대표" if i==0 else f"본문{i}",
                        "en":f"visual for section {i} of '{topic}'",
                        "ko":f"본문 섹션 {i} 보조 이미지"})
    blog["images"] = prompts
    return blog

# ====== 내보내기 포맷 ======
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

# ====== 실행 버튼 처리 ======
if go:
    try:
        do_yt   = target in ["유튜브 + 블로그","유튜브만"]
        do_blog = target in ["유튜브 + 블로그","블로그만"]
        results={}
        with st.spinner("생성 중입니다…"):
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futs=[]
                if do_yt:   futs.append(("yt",   ex.submit(gen_youtube, topic, tone, target_chapter, mode)))
                if do_blog: futs.append(("blog", ex.submit(gen_blog, topic, tone, mode, blog_min, blog_imgs)))
                for name,f in futs: results[name]=f.result()

        # === 유튜브 출력 ===
        if do_yt:
            st.markdown("## 📺 유튜브 패키지")
            yt=results.get("yt",{})

            # ① SEO 제목 10
            titles=[f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:10])]
            st.markdown("**① 영상 제목(SEO 10)**")
            copy_block("영상 제목 복사", "\n".join(titles), 160, use_copy_button)

            # ② 영상 설명
            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", yt.get("description",""), 160, use_copy_button)

            # ③ 브루 자막 — 전체 일괄 복사 (Vrew용)
            chapters = yt.get("chapters", [])[:target_chapter]
            full_vrew_script = "\n".join([c.get("script", "").replace("\n", " ") for c in chapters])
            st.markdown("**③ 브루 자막 — 전체 일괄 복사 (Vrew)**")
            copy_block("브루 자막 — 전체 일괄", full_vrew_script, 220, use_copy_button)

            # (옵션) 챕터별 개별 복사
            if show_chapter_blocks:
                exp = st.expander("챕터별 자막 복사 (펼쳐서 보기)", expanded=False)
                with exp:
                    for i,c in enumerate(chapters,1):
                        copy_block(f"[챕터 {i}] {c.get('title',f'챕터 {i}')}", c.get("script",""), 140, use_copy_button)

            # ④ 이미지 프롬프트 (썸네일 + 챕터)
            st.markdown("**④ 이미지 프롬프트 (썸네일 + 챕터)**")
            if include_thumb:
                copy_block("[썸네일] EN",
                           build_kr_image_en(
                               f"YouTube thumbnail for topic: {topic}. Korean title area, high contrast.",
                               final_age, final_gender, img_place, img_mood, img_shot, img_style),
                           110, use_copy_button)
                copy_block("[썸네일] KO",
                           f"{final_age} {final_gender} 한국인이 {img_place}에서 주제 '{topic}'를 표현, {img_mood} 분위기, {img_style} {img_shot} — 큰 한글 제목 영역",
                           90, use_copy_button)

            if show_img_blocks:
                ips=(yt.get("images",{}) or {}).get("chapters",[])
                if len(ips)<len(chapters):
                    for i in range(len(ips),len(chapters)):
                        ips.append({"index":i+1,"en":"support","ko":"보조"})
                expi=st.expander("챕터별 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                with expi:
                    for i,p in enumerate(ips[:target_chapter],1):
                        copy_block(f"[챕터 {i}] EN",
                                   build_kr_image_en(p.get("en",""), final_age, final_gender, img_place, img_mood, img_shot, img_style),
                                   110, use_copy_button)
                        ko_text = p.get("ko","") or f"{final_age} {final_gender} 한국인이 {img_place}에서 '{chapters[i-1].get('title','')}' 표현, {img_mood} {img_style} {img_shot}"
                        copy_block(f"[챕터 {i}] KO", ko_text, 90, use_copy_button)

            # ⑤ 해시태그(20)
            st.markdown("**⑤ 해시태그(20)**")
            copy_block("해시태그 복사", " ".join(yt.get("hashtags",[])), 90, use_copy_button)

            # ⬇️ 내보내기(.txt)
            st.download_button("⬇️ 유튜브 패키지 .txt 저장",
                               build_youtube_txt(yt).encode("utf-8"),
                               file_name="youtube_package.txt", mime="text/plain",
                               key=f"dl_yt_{uuid.uuid4().hex}")

        # === 블로그 출력 ===
        if do_blog:
            st.markdown("---"); st.markdown("## 📝 블로그 패키지")
            blog=results.get("blog",{})

            # ① 블로그 제목(SEO 10)
            bts=[f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:10])]
            st.markdown("**① 블로그 제목(SEO 10)**")
            copy_block("블로그 제목 복사", "\n".join(bts), 160, use_copy_button)

            # ② 본문 (강화 · 2,200자+)
            st.markdown("**② 본문 (강화 · 2,200자+)**")
            copy_block("블로그 본문 복사", blog.get("body",""), 420, use_copy_button)

            # ③ 이미지 프롬프트 (EN + KO)
            st.markdown("**③ 이미지 프롬프트 (EN + KO)**")
            if show_img_blocks:
                expb = st.expander("블로그 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                with expb:
                    for p in blog.get("images",[]):
                        copy_block(f"[{p.get('label','이미지')}] EN",
                                   build_kr_image_en(p.get("en",""), final_age, final_gender, img_place, img_mood, img_shot, img_style),
                                   110, use_copy_button)
                        copy_block(f"[{p.get('label','이미지')}] KO", p.get("ko",""), 90, use_copy_button)

            # ④ 태그(20)
            st.markdown("**④ 태그(20)**")
            copy_block("블로그 태그 복사", "\n".join(blog.get("tags",[])), 100, use_copy_button)

            # ⬇️ 내보내기(.md)
            st.download_button("⬇️ 블로그 패키지 .md 저장",
                               build_blog_md(blog).encode("utf-8"),
                               file_name="blog_package.md", mime="text/markdown",
                               key=f"dl_blog_{uuid.uuid4().hex}")

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그를 확인해주세요.")
        st.exception(e)

st.markdown("---")
st.caption("한국인 고정 · 주제 기반 자동 연령/성별 · Vrew 자막 일괄복사 · 정보형/영업형 CTA 분기 · 이미지 프롬프트 · 복사 버튼/내보내기 · 병렬/캐싱.")
