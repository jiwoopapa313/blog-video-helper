# app.py — 속도 최적화 통합 생성기 (Korean Senior • Async/Cache/Safe/Export)
# OPENAI_API_KEY 는 Streamlit Secrets 또는 환경변수에 설정

import os, json, time, uuid, html
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from openai import OpenAI
from streamlit.components.v1 import html as comp_html

# =============================
# 🔒 안전/진단/성능 토글
# =============================
SAFE_BOOT      = True      # True: UI 먼저 → 버튼 누를 때만 생성(무한 로딩 방지)
USE_COPY_BTN   = True      # 복사 버튼(iframe) 사용. 문제시 False로 바꾸면 세이프 복사 박스
OFFLINE_MOCK   = False     # True: OpenAI 호출 없이 샘플 출력으로 UI만 검증
DEBUG_PING     = True      # 페이지 상단 READY 표시
MAX_WORKERS    = 2         # 유튜브/블로그 병렬 생성 스레드 수

# =============================
# 기본 세팅
# =============================
KST = timezone(timedelta(hours=9))
st.set_page_config(page_title="블로그·유튜브 통합 생성기(최적화)", page_icon="⚡", layout="wide")
st.title("⚡ 블로그·유튜브 통합 생성기 (속도 최적화판)")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 병렬 생성 · 캐싱 · 고유 key · 세이프부팅 · 내보내기")

if DEBUG_PING:
    st.write("✅ READY")

if SAFE_BOOT:
    st.info("세이프 부팅: 옵션 확인 후 **[▶ 한 번에 생성]** 버튼을 눌러 실행합니다.")

CTA = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

# =============================
# 복사 블록 (iframe) / 세이프 모드
# =============================
def copy_block_iframe(title: str, text: str, height: int = 160):
    esc_t = (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    _key = f"copy_iframe_{uuid.uuid4().hex}"   # 🔑 고유 key로 DOM 충돌 방지
    comp_html(f"""
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
  <textarea id="ta" readonly>{esc_t}</textarea>
  <div class="row">
    <button class="btn" id="copyBtn">📋 복사</button>
    <small>안 되면 텍스트 클릭 → Ctrl+A → Ctrl+C</small>
  </div>
</div>
<script>
(()=>{{const b=document.getElementById("copyBtn");const t=document.getElementById("ta");
if(!b||!t)return;b.onclick=async()=>{{try{{await navigator.clipboard.writeText(t.value);
b.textContent="✅ 복사됨";setTimeout(()=>b.textContent="📋 복사",1200)}}catch(e){{try{{t.focus();t.select();document.execCommand("copy");
b.textContent="✅ 복사됨";setTimeout(()=>b.textContent="📋 복사",1200)}}catch(err){{alert("복사가 차단되었습니다. 직접 선택하여 복사해주세요.")}}}}}})();
</script></body></html>
    """, height=height+110, scrolling=False, key=_key)

def copy_block_safe(title: str, text: str, height: int = 160):
    st.markdown(f"**{title or ''}**")
    st.text_area("", text or "", height=height, key="ta_"+uuid.uuid4().hex)
    st.caption("복사: 영역 클릭 → Ctrl+A → Ctrl+C (모바일은 길게 눌러 전체 선택)")

def copy_block(title: str, text: str, height: int = 160, use_button: bool = True):
    use_button = use_button and USE_COPY_BTN
    (copy_block_iframe if use_button else copy_block_safe)(title, text, height)

# =============================
# OpenAI / 재시도 / 캐시
# =============================
def _client():
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key and not OFFLINE_MOCK:
        st.warning("🔐 OPENAI_API_KEY가 없습니다. Secrets/환경변수에 설정해주세요.", icon="⚠️")
    return OpenAI(api_key=api_key) if api_key else None

def _retry(fn, *a, **kw):
    waits = [0.7, 1.2, 2.2, 3.6]
    err = None
    for i,w in enumerate(waits):
        try: return fn(*a, **kw)
        except Exception as e:
            err = e
            if i < len(waits)-1: time.sleep(w)
    raise err

@st.cache_data(show_spinner=False)
def chat_cached(system, user, model, temperature):
    if OFFLINE_MOCK:
        return "{}"
    c = _client()
    if not c: return "{}"
    def call():
        return c.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
        )
    r = _retry(call)
    return r.choices[0].message.content.strip()

def json_complete(system, user, model, temperature, fallback: dict):
    raw = chat_cached(system, user, model, temperature)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or not data:
            return fallback
        return data
    except Exception:
        raw2 = chat_cached(system + " RETURN JSON ONLY. NO PROSE.", user, model, 0.3)
        try:
            data2 = json.loads(raw2)
            if not isinstance(data2, dict) or not data2:
                return fallback
            return data2
        except Exception:
            return fallback

# =============================
# K-시니어 이미지 EN 프롬프트 빌더
# =============================
def build_kr_image_en(subject_en: str,
                      img_age: str, img_gender: str, img_place: str,
                      img_mood: str, img_shot: str, img_style: str) -> str:
    age_map={"50대":"in their 50s","60대":"in their 60s","70대":"in their 70s"}
    gender={"남성":"Korean man","여성":"Korean woman"}.get(img_gender,"Korean seniors (men and women)")
    place={"한국 가정 거실":"modern Korean home living room interior",
           "한국 아파트 단지":"Korean apartment complex outdoor area",
           "한국 동네 공원":"local Korean neighborhood park",
           "한국 병원/검진센터":"Korean medical clinic or health screening center interior",
           "한국형 주방/식탁":"modern Korean kitchen and dining table"}
    shot={"클로즈업":"close-up","상반신":"medium shot","전신":"full body shot","탑뷰/테이블샷":"top view table shot"}
    mood={"따뜻한":"warm","밝은":"bright","차분한":"calm","활기찬":"energetic"}
    style={"사진 실사":"realistic photography, high resolution",
           "시네마틱":"cinematic photo style, soft depth of field",
           "잡지 화보":"editorial magazine style",
           "자연광":"natural lighting, soft daylight"}
    return (f"{gender} {age_map.get(img_age,'in their 50s')} at a {place.get(img_place,'modern Korean interior')}, "
            f"{shot.get(img_shot,'medium shot')}, {mood.get(img_mood,'warm')} mood, "
            f"{style.get(img_style,'realistic photography, high resolution')}. "
            f"Context: {subject_en}. Korean ethnicity visible, Asian facial features, natural skin tone; "
            f"subtle Korean signage/items. Avoid Western features.")

# =============================
# 사이드바 옵션
# =============================
with st.sidebar:
    st.header("⚙️ 생성 설정")
    model_text = st.selectbox("모델", ["gpt-4o-mini","gpt-4o"], index=0)
    temperature = st.slider("창의성", 0.0, 1.2, 0.6, 0.1)
    polish = st.checkbox("후가공(4o로 문장 다듬기)", value=False)

    st.markdown("---")
    target_chapter = st.selectbox("유튜브 자막 개수", [5,6,7], 0)
    include_thumb = st.checkbox("썸네일 프롬프트 포함", value=True)

    st.markdown("---")
    st.markdown("### 🖼 한국 시니어 이미지 프리셋")
    img_age = st.selectbox("연령", ["50대","60대","70대"], 0)
    img_gender = st.selectbox("성별", ["혼합","남성","여성"], 0)
    img_place = st.selectbox("장소", ["한국 가정 거실","한국 아파트 단지","한국 동네 공원","한국 병원/검진센터","한국형 주방/식탁"], 0)
    img_mood = st.selectbox("무드", ["따뜻한","밝은","차분한","활기찬"], 0)
    img_shot = st.selectbox("샷", ["클로즈업","상반신","전신","탑뷰/테이블샷"], 1)
    img_style = st.selectbox("스타일", ["사진 실사","시네마틱","잡지 화보","자연광"], 0)

    st.markdown("---")
    st.markdown("### 📝 블로그 강화")
    blog_min = st.slider("최소 길이(자)", 1500, 4000, 2200, 100)
    blog_imgs = st.selectbox("이미지 프롬프트 수", [3,4,5,6], index=2)

    st.markdown("---")
    st.markdown("### 🧩 화면 부하 줄이기")
    show_chapter_blocks = st.checkbox("자막 개별 복사 블록 표시", value=False)
    show_img_blocks     = st.checkbox("챕터/블로그 이미지 프롬프트 표시", value=False)
    use_copy_button     = st.radio("복사 방식", ["복사 버튼","세이프(수동 복사)"], 0) == "복사 버튼"

    st.markdown("---")
    force_refresh = st.checkbox("강제 재생성(캐시 무시)", value=False)

# =============================
# 입력 폼
# =============================
st.subheader("🎯 주제 및 내용")
c1,c2,c3,c4 = st.columns([2,1,1,1])
with c1: topic = st.text_input("주제", value="관악구 봉천동 동아아파트 변기부속 교체시공")
with c2: tone  = st.selectbox("톤/스타일", ["시니어 친화형","전문가형","친근한 설명형"], 1)
with c3: mode_sel = st.selectbox("콘텐츠 유형", ["자동 분류","정보형(블로그 지수)","시공후기형(영업)"], 2)
with c4: target = st.selectbox("생성 대상", ["유튜브 + 블로그","유튜브만","블로그만"], 0)

def classify(txt):
    return "sales" if any(k in txt for k in ["시공","교체","설치","수리","누수","보수","후기","현장","관악","강쌤철물"]) else "info"
def ensure_mode():
    if mode_sel=="정보형(블로그 지수)": return "info"
    if mode_sel=="시공후기형(영업)":   return "sales"
    return classify(topic)

mode = ensure_mode()

# 캐시 버스터(재생성)
if force_refresh:
    st.cache_data.clear()

go = st.button("▶ 한 번에 생성", type="primary")

# =============================
# 내보내기(.txt/.md) 헬퍼
# =============================
def build_youtube_txt(yt: dict) -> str:
    titles = "\n".join(f"{i+1}. {t}" for i,t in enumerate(yt.get('titles',[])[:3]))
    chapters = "\n\n".join(f"[챕터 {i+1}] {c.get('title','')}\n{c.get('script','')}"
                           for i,c in enumerate(yt.get('chapters',[])))
    desc = yt.get('description','').strip()
    tags = " ".join(yt.get('hashtags',[]))
    return f"""# YouTube Package
## Titles
{titles}

## Description
{desc}

## Chapters
{chapters}

## Hashtags
{tags}
"""

def build_blog_md(blog: dict) -> str:
    titles = "\n".join(f"{i+1}. {t}" for i,t in enumerate(blog.get('titles',[])[:3]))
    body = blog.get('body','')
    tags = " ".join(blog.get('hashtags',[]))
    return f"""# Blog Package
## Titles
{titles}

## Body
{body}

## Tags
{tags}
"""

# =============================
# 스키마 문자열 (LLM용)
# =============================
def _schema_for_llm():
    # f-string 충돌 방지를 위해 별도 문자열로 유지
    return r'''{
  "titles": ["...", "...", "..."],
  "description": "(3~5줄 한국어)",
  "chapters": [{"title":"Tip1","script":"..."}],
  "image_prompts": [{"label":"Chap1","en":"...","ko":"..."}],
  "hashtags": ["#..", "#..", "#..", "#.."]
}'''

# =============================
# 생성 함수들
# =============================
def gen_youtube(topic, tone, n, mode):
    if OFFLINE_MOCK:
        return {
            "titles": [f"{topic} 핵심 요약", f"{topic} 필수 팁", f"{topic} 이렇게 하세요"],
            "description": f"{topic}에 대한 3~5줄 샘플 설명입니다.",
            "chapters": [{"title":f"Tip{i+1}","script":f"{topic} 관련 핵심 팁 {i+1} 설명(샘플)."} for i in range(n)],
            "image_prompts": [{"label":f"Chap{i+1}","en":"sample visual","ko":"샘플 이미지"} for i in range(n)],
            "hashtags": ["#시공후기","#관악구","#강쌤철물"]
        }

    sys = (
        "You are a seasoned Korean YouTube scriptwriter for seniors. "
        "Return STRICT JSON only. Make EXACTLY N chapters (2–4 sentences each). "
        "Include image_prompts aligned 1:1 with chapters. "
        "Prompts must depict Korean seniors in Korean settings (avoid Western)."
    )
    user = (
        f"[주제] {topic}\n"
        f"[톤] {tone}\n"
        f"[N] {n}\n"
        f"[유형] {('정보형' if mode=='info' else '시공후기형(영업)')}\n\n"
        f"[JSON schema]\n{_schema_for_llm()}\n"
        "- 'chapters'와 'image_prompts'는 길이 N으로 맞추고(1:1), 항목은 한국어 문장.\n"
        "- 정보형은 CTA 금지, 영업형은 앱이 설명 마지막 줄에 CTA를 자동 추가.\n"
    )

    fallback = {
        "titles": [f"{topic} 가이드", f"{topic} 핵심정리", f"{topic} 쉽게 따라하기"],
        "description": f"{topic} 설명(폴백).",
        "chapters": [{"title":f"Tip{i+1}","script":f"{topic} 팁 {i+1} (폴백)"} for i in range(n)],
        "image_prompts": [{"label":f"Chap{i+1}","en":"fallback","ko":"폴백"} for i in range(n)],
        "hashtags": ["#폴백","#샘플"]
    }

    data = json_complete(sys, user, model_text, temperature, fallback)

    # 정합성 보정
    ch = data.get("chapters", [])[:n]
    ip = data.get("image_prompts", [])[:n]
    while len(ch) < n:
        ch.append({"title": f"Tip{len(ch)+1}", "script": "간단한 보충 설명."})
    while len(ip) < n:
        i = len(ip); ip.append({"label": f"Chap{i+1}","en": f"visual for chapter {i+1} of '{topic}'","ko":f"챕터 {i+1} 보조 이미지"})
    data["chapters"], data["image_prompts"] = ch, ip

    # 선택 후가공
    if polish:
        try:
            data = json.loads(chat_cached(
                "Polish Korean text for clarity; keep JSON shape/counts. RETURN JSON ONLY.",
                json.dumps(data, ensure_ascii=False),
                "gpt-4o", 0.4
            ))
        except Exception: pass

    # 영업형 CTA
    if mode == "sales":
        desc = data.get("description","").rstrip()
        if CTA not in desc:
            data["description"] = (desc + f"\n{CTA}").strip()

    return data

def gen_blog(topic, tone, mode, min_chars, img_count):
    if OFFLINE_MOCK:
        body = (
            f"### 서론\n{topic} 샘플 본문.\n\n"
            f"### 핵심 5가지\n1) 핵심 A\n2) 핵심 B\n3) 핵심 C\n4) 핵심 D\n5) 핵심 E\n\n"
            f"### 체크리스트\n- [ ] 체크1\n- [ ] 체크2\n- [ ] 체크3\n- [ ] 체크4\n- [ ] 체크5\n- [ ] 체크6\n\n"
            f"### 자가진단\n1) 예/아니오 1\n2) 예/아니오 2\n3) 예/아니오 3\n4) 예/아니오 4\n5) 예/아니오 5\n\n"
            f"### FAQ\nQ1. 샘플?\nA1. 네.\nQ2. 예시?\nA2. 네.\nQ3. 적용?\nA3. 가능합니다.\n\n"
            f"### 마무리\n요약."
        )
        if mode == "sales":
            body += f"\n\n{CTA}"
        return {
            "titles": [f"{topic} 완벽 가이드", f"{topic} 핵심 체크리스트", f"{topic} 이렇게 관리"],
            "body": body,
            "image_prompts": [{"label":"대표","en":"sample","ko":"샘플"}] + [{"label":f"본문{i}","en":"sample","ko":"샘플"} for i in range(1, img_count)],
            "hashtags": ["#시공후기","#관악구","#강쌤철물"]
        }

    sys = (
        "You are a Korean Naver-SEO writer. RETURN STRICT JSON ONLY. "
        f"Body MUST be >= {min_chars} Korean characters and include 3~5 '[이미지: ...]' markers. "
        "Sections: 서론 → 핵심 5가지(번호목록) → 체크리스트(6~8) → 자가진단 5(예/아니오) → FAQ 3(문답) → 마무리. "
        "정보형은 CTA 금지, 영업형은 마지막 1줄 CTA 허용."
    )

    ip = [{"label":"대표","en":"...","ko":"..."}] + [{"label":f"본문{i}","en":"...","ko":"..."} for i in range(1, img_count)]

    user = (
        f"[주제] {topic}\n"
        f"[톤] {tone}\n"
        f"[유형] {('정보형' if mode=='info' else '시공후기형(영업)')}\n"
        f"[최소길이] {min_chars}\n"
        f"[이미지개수] {img_count}\n\n"
        f'[JSON schema]\n{{\n'
        f'  "titles": ["...", "...", "..."],\n'
        f'  "body": "(서론/핵심5/체크리스트/자가진단/FAQ/마무리 · {min_chars}+자 · [이미지: ...] 3~5)",\n'
        f'  "image_prompts": {json.dumps(ip, ensure_ascii=False)},\n'
        f'  "hashtags": ["#..", "#..", "#..", "#..", "#..", "#..", "#.."]\n'
        f"}}\n"
    )

    fallback = {
        "titles": [f"{topic} 가이드", f"{topic} 체크리스트", f"{topic} 핵심정리"],
        "body": f"{topic} 폴백 본문",
        "image_prompts": ip,
        "hashtags": ["#폴백","#샘플"]
    }

    data = json_complete(sys, user, model_text, temperature, fallback)

    # 길이 보정
    body = data.get("body","")
    if len(body) < min_chars:
        try:
            data = json.loads(chat_cached(
                f"Expand to >={min_chars+300} Korean characters; keep structure & markers; RETURN JSON ONLY.",
                json.dumps(data, ensure_ascii=False),
                model_text, 0.5
            ))
        except Exception: pass

    # 선택 후가공
    if polish:
        try:
            data = json.loads(chat_cached(
                "Polish Korean; keep structure/counts; RETURN JSON ONLY.",
                json.dumps(data, ensure_ascii=False),
                "gpt-4o", 0.4
            ))
        except Exception: pass

    # CTA 처리
    body = data.get("body","")
    if mode == "sales" and CTA not in body:
        data["body"] = body.rstrip() + f"\n\n{CTA}"
    if mode == "info" and CTA in body:
        data["body"] = body.replace(CTA,"").strip()

    # 이미지 프롬프트 개수 보정
    prompts = data.get("image_prompts", [])[:img_count]
    while len(prompts) < img_count:
        i = len(prompts)
        prompts.append({"label":"대표" if i==0 else f"본문{i}",
                        "en":f"visual for section {i} of '{topic}'",
                        "ko":f"본문 섹션 {i} 보조 이미지"})
    data["image_prompts"] = prompts
    return data

# =============================
# 실행(병렬)
# =============================
if go:
    try:
        do_yt   = target in ["유튜브 + 블로그","유튜브만"]
        do_blog = target in ["유튜브 + 블로그","블로그만"]

        results = {}
        tasks = []

        with st.spinner("생성 중입니다…"):
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                if do_yt:
                    tasks.append(("yt", ex.submit(gen_youtube, topic, tone, target_chapter, mode)))
                if do_blog:
                    tasks.append(("blog", ex.submit(gen_blog, topic, tone, mode, blog_min, blog_imgs)))
                for name, fut in tasks:
                    results[name] = fut.result()

        # ===== 유튜브 출력 =====
        if do_yt:
            st.markdown("## 📺 유튜브 패키지")
            yt = results.get("yt", {})

            with st.container():
                st.markdown("**① 영상 제목 3개**")
                titles = [f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:3])]
                copy_block("영상 제목 복사", "\n".join(titles), 110, use_copy_button)

                st.markdown("**② 영상 설명**")
                copy_block("영상 설명 복사", yt.get("description",""), 160, use_copy_button)

                st.markdown("**③ 브루 자막 (전체 일괄)**")
                ch = yt.get("chapters",[])[:target_chapter]
                all_scripts = [c.get("script","") for c in ch]
                copy_block("브루 자막 — 전체 일괄", "\n\n".join(all_scripts), 220, use_copy_button)

                if show_chapter_blocks:
                    exp = st.expander("챕터별 자막 복사 (펼쳐서 보기)", expanded=False)
                    with exp:
                        for i,c in enumerate(ch,1):
                            copy_block(f"[챕터 {i}] {c.get('title',f'챕터 {i}')}",
                                       c.get("script",""), 140, use_copy_button)

                st.markdown("**④ 이미지 프롬프트**")
                if include_thumb:
                    copy_block(
                        "[썸네일] EN",
                        build_kr_image_en(f"YouTube thumbnail for topic: {topic}. Korean title area, high contrast.",
                                          img_age, img_gender, img_place, img_mood, img_shot, img_style),
                        110, use_copy_button
                    )
                    copy_block(
                        "[썸네일] KO",
                        f"{img_age} {img_gender} 한국인이 {img_place}에서 {img_mood} 분위기, {img_style} {img_shot} — 큰 한글 제목 영역",
                        90, use_copy_button
                    )

                if show_img_blocks:
                    ips = yt.get("image_prompts",[])[:target_chapter]
                    if len(ips) < len(ch):
                        for i in range(len(ips), len(ch)):
                            ips.append({"label":f"Chap{i+1}","en":"support","ko":"보조"})
                    expi = st.expander("챕터별 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                    with expi:
                        for i,p in enumerate(ips,1):
                            copy_block(f"[챕터 {i}] EN",
                                       build_kr_image_en(p.get("en",""),
                                                         img_age, img_gender, img_place, img_mood, img_shot, img_style),
                                       110, use_copy_button)
                            ko_text = p.get("ko","") or f"{img_age} {img_gender} 한국인이 {img_place}에서 '{ch[i-1].get('title','')}' 표현, {img_mood} {img_style} {img_shot}"
                            copy_block(f"[챕터 {i}] KO", ko_text, 90, use_copy_button)

                st.markdown("**⑤ 해시태그**")
                copy_block("해시태그 복사", " ".join(yt.get("hashtags",[])), 80, use_copy_button)

                # ⬇️ ⑥ 내보내기(.txt)
                yt_txt = build_youtube_txt(yt)
                st.download_button(
                    "⬇️ 유튜브 패키지 .txt 저장", yt_txt.encode("utf-8"),
                    file_name="youtube_package.txt", mime="text/plain",
                    key=f"dl_yt_{uuid.uuid4().hex}"
                )

        # ===== 블로그 출력 =====
        if do_blog:
            st.markdown("---")
            st.markdown("## 📝 블로그 패키지")
            blog = results.get("blog", {})

            with st.container():
                st.markdown("**① 블로그 제목 3개**")
                bts = [f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:3])]
                copy_block("블로그 제목 복사", "\n".join(bts), 110, use_copy_button)

                st.markdown("**② 본문 (강화 · 2,200자+)**")
                copy_block("블로그 본문 복사", blog.get("body",""), 420, use_copy_button)

                st.markdown("**③ 이미지 프롬프트 (EN + KO)**")
                if show_img_blocks:
                    expb = st.expander("블로그 이미지 프롬프트 (펼쳐서 보기)", expanded=False)
                    with expb:
                        for p in blog.get("image_prompts",[])[:blog_imgs]:
                            copy_block(f"[{p.get('label','이미지')}] EN",
                                       build_kr_image_en(p.get("en",""),
                                                         img_age, img_gender, img_place, img_mood, img_shot, img_style),
                                       110, use_copy_button)
                            copy_block(f"[{p.get('label','이미지')}] KO", p.get("ko",""), 90, use_copy_button)

                st.markdown("**④ 해시태그**")
                copy_block("블로그 태그 복사", "\n".join(blog.get("hashtags",[])), 100, use_copy_button)

                # ⬇️ ⑤ 내보내기(.md)
                blog_md = build_blog_md(blog)
                st.download_button(
                    "⬇️ 블로그 패키지 .md 저장", blog_md.encode("utf-8"),
                    file_name="blog_package.md", mime="text/markdown",
                    key=f"dl_blog_{uuid.uuid4().hex}"
                )

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그를 확인해주세요.")
        st.exception(e)

st.markdown("---")
st.caption("병렬 생성·캐싱·세이프부팅. 정보형은 CTA 자동 제거, 영업형은 CTA 자동 삽입. K-시니어 프리셋 강제. 내보내기(.txt/.md) 지원.")
