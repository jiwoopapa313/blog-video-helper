# app.py — Safe Boot (빈 화면 방지 · 버튼 누를 때만 생성 실행 · JS/컴포넌트 미사용)
# 필요: Streamlit Secrets 또는 환경변수 OPENAI_API_KEY

import os, json, time, uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from openai import OpenAI

KST = timezone(timedelta(hours=9))
st.set_page_config(page_title="블로그·유튜브 통합 생성기 (Safe Boot)", page_icon="🧰", layout="wide")

# ----- 항상 먼저 화면에 나오는 최소 UI (하얀 화면 방지) -----
st.title("🧰 블로그·유튜브 통합 생성기 — Safe Boot")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · JS/컴포넌트 미사용 · 빈화면 방지 모드")

# ====== 공통 유틸 ======
def get_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("🔐 OPENAI_API_KEY가 없습니다. Streamlit Secrets에 추가해 주세요.", icon="⚠️")
    return OpenAI(api_key=api_key) if api_key else None

def retry_call(call_fn):
    waits = [0.7, 1.2, 2.0, 3.5]
    err = None
    for i, w in enumerate(waits):
        try:
            return call_fn()
        except Exception as e:
            err = e
            if i < len(waits) - 1:
                time.sleep(w)
    if err:
        raise err

def chat(system, user, model="gpt-4o-mini", temperature=0.6):
    cli = get_client()
    if not cli:
        st.stop()
    def _do():
        return cli.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
        )
    res = retry_call(_do)
    return res.choices[0].message.content.strip()

# ====== 사이드바 (전부 기본 위젯만 사용) ======
with st.sidebar:
    st.header("⚙️ 생성 설정")
    model_text = st.selectbox("텍스트 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.6, 0.1)

    st.markdown("---")
    st.markdown("### 🎬 자막/이미지 동기화")
    chapter_n = st.selectbox("자막(챕터) 개수", [5, 6, 7], index=0)
    thumbnail_opt = st.checkbox("썸네일 프롬프트 포함", value=True)

    st.markdown("---")
    st.markdown("### 🖼 이미지 프리셋(한국 시니어)")
    img_age = st.selectbox("연령대", ["50대", "60대", "70대"], 0)
    img_gender = st.selectbox("성별", ["혼합", "남성", "여성"], 0)
    img_place  = st.selectbox("장소/배경", ["한국 가정 거실","한국 아파트 단지","한국 동네 공원","한국 병원/검진센터","한국형 주방/식탁"], 0)
    img_mood   = st.selectbox("무드", ["따뜻한","밝은","차분한","활기찬"], 0)
    img_shot   = st.selectbox("샷", ["클로즈업","상반신","전신","탑뷰/테이블샷"], 1)
    img_style  = st.selectbox("스타일", ["사진 실사","시네마틱","잡지 화보","자연광"], 0)

# ====== 입력 ======
st.subheader("🎯 주제 & 유형")
c1, c2, c3, c4 = st.columns([2,1,1,1])
with c1:
    topic = st.text_input("주제", value="치매 예방 두뇌 건강법")
with c2:
    tone  = st.selectbox("톤/스타일", ["시니어 친화형","전문가형","친근한 설명형"], 0)
with c3:
    mode_sel = st.selectbox("콘텐츠 유형", ["자동 분류","정보형(블로그 지수)","시공후기형(영업)"], 0)
with c4:
    target   = st.selectbox("생성 대상", ["유튜브 + 블로그","유튜브만","블로그만"], 0)

def simple_classify(text):
    for k in ["시공","교체","설치","수리","누수","보수","후기","현장","관악","강쌤철물"]:
        if k in text: return "sales"
    return "info"

def get_mode():
    if mode_sel == "정보형(블로그 지수)": return "info"
    if mode_sel == "시공후기형(영업)":   return "sales"
    return simple_classify(topic)

mode = get_mode()
CTA  = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

# ====== “텍스트 영역만” 복사 블록 (완전 안전) ======
def copy_block(title: str, text: str, height: int = 160):
    st.markdown(f"**{title}**")
    st.text_area("", text or "", height=height, key="ta_"+uuid.uuid4().hex)
    st.caption("복사: 박스 클릭 → Ctrl+A → Ctrl+C (모바일은 길게 눌러 전체 선택)")

# ====== 이미지 프리셋 EN 빌더 ======
def build_img_en(subject_en):
    age_map = {"50대":"in their 50s","60대":"in their 60s","70대":"in their 70s"}
    age_en  = age_map.get(img_age, "in their 50s")
    gender_en = {"남성":"Korean man","여성":"Korean woman"}.get(img_gender, "Korean seniors (men and women)")
    place_map = {
        "한국 가정 거실":"modern Korean home living room interior",
        "한국 아파트 단지":"Korean apartment complex outdoor area",
        "한국 동네 공원":"local Korean neighborhood park",
        "한국 병원/검진센터":"Korean medical clinic or health screening center interior",
        "한국형 주방/식탁":"modern Korean kitchen and dining table",
    }
    shot_map = {"클로즈업":"close-up","상반신":"medium shot","전신":"full body shot","탑뷰/테이블샷":"top view table shot"}
    mood_map = {"따뜻한":"warm","밝은":"bright","차분한":"calm","활기찬":"energetic"}
    style_map= {
        "사진 실사":"realistic photography, high resolution",
        "시네마틱":"cinematic photo style, soft depth of field",
        "잡지 화보":"editorial magazine style",
        "자연광":"natural lighting, soft daylight",
    }
    return (
        f"{gender_en} {age_en} at a {place_map.get(img_place,'modern Korean interior')}, "
        f"{shot_map.get(img_shot,'medium shot')}, {mood_map.get(img_mood,'warm')} mood, "
        f"{style_map.get(img_style,'realistic photography, high resolution')}. "
        f"Context: {subject_en}. Korean ethnicity, Asian facial features, natural skin tone, "
        "avoid Western features"
    )

# ====== 생성 버튼 ======
go = st.button("▶ 모두 생성", type="primary")

# ====== 안전한 실행 래퍼 ======
def safe_json(system, user):
    raw = chat(system, user, model_text, temperature)
    try:
        return json.loads(raw)
    except Exception:
        # 모델이 텍스트 섞으면 강제 JSON 재요청
        raw2 = chat(system+" RETURN JSON ONLY.", user, model_text, 0.4)
        return json.loads(raw2)

# ====== 유튜브/블로그 생성기 ======
def make_youtube():
    sys = (
        "You are a seasoned Korean YouTube writer for seniors. "
        "Return STRICT JSON only. Titles first, hashtags last. "
        "Create EXACTLY N content chapters (2~4 sentences each). "
        "Image prompts must describe Korean seniors in Korean settings; include EN + KO."
    )
    user = f"""
[주제] {topic}
[톤] {tone}
[유형] {"정보형" if mode=="info" else "시공후기형(영업)"}
[N] {chapter_n}
[요구 스키마]
{{
 "titles": ["...","...","..."],
 "description": "(3~5줄){' 마지막 줄에 CTA: '+CTA if mode=='sales' else ''}",
 "chapters": [{{"title":"...","script":"..."}}, ... N개],
 "image_prompts": [{{"label":"Chap1","en":"...","ko":"..."}}, ... N개],
 "hashtags": ["#..","#..","#..","#..","#..","#.."]
}}
- 'chapters'와 'image_prompts'는 N개로 index 1:1 정렬.
- CTA는 info 모드에서는 절대 넣지 마세요.
"""
    data = safe_json(sys, user)

    # 출력
    st.markdown("## 📺 유튜브 패키지 — 제목→설명→자막→이미지→태그")

    titles = [f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]
    copy_block("① 영상 제목 복사", "\n".join(titles), 110)

    copy_block("② 영상 설명 복사", data.get("description",""), 160)

    chs = data.get("chapters", [])[:chapter_n]
    all_lines = []
    st.markdown("**③ 브루 자막 (챕터별 + 전체 복사)**")
    for i, ch in enumerate(chs, 1):
        s = ch.get("script","")
        all_lines.append(s)
        copy_block(f"[챕터 {i}] {ch.get('title','')}", s, 140)
    copy_block("브루 자막 — 전체 일괄 복사", "\n\n".join(all_lines), 220)

    st.markdown("**④ 이미지 프롬프트 (EN + KO) — 자막과 동일 개수**")
    if thumbnail_opt:
        copy_block("[썸네일] EN", build_img_en(f"YouTube thumbnail for topic: {topic}. Clear big Korean title space, high contrast."), 110)
        copy_block("[썸네일] KO", f"{img_age} {img_gender} 한국인이 {img_place}에서 {img_mood} 분위기, {img_style} {img_shot} — 한글 큰 제목 영역 확보, 고대비", 90)

    imps = data.get("image_prompts", [])[:chapter_n]
    for i, p in enumerate(imps, 1):
        en_base = p.get("en","")
        copy_block(f"[챕터 {i}] EN (Korean preset enforced)", build_img_en(en_base), 110)
        copy_block(f"[챕터 {i}] KO", p.get("ko",""), 90)

    copy_block("⑤ 해시태그 복사", " ".join(data.get("hashtags", [])), 80)

def make_blog():
    sys = (
        "You are a Korean Naver-SEO writer. Return STRICT JSON only. "
        "Body must be >=1500 Korean characters with short paragraphs, lists and 2~3 [이미지: ...] markers. "
        "Info: never include CTA. Sales: add short CTA at the very end."
    )
    user = f"""
[주제] {topic}
[톤] {tone}
[유형] {"정보형" if mode=="info" else "시공후기형(영업)"}
[스키마]
{{
 "titles": ["...","...","..."],
 "body": "(>=1500자 · 소제목/목록 · [이미지: ...] 2~3곳)",
 "image_prompts": [
    {{"label":"대표","en":"...","ko":"..."}},
    {{"label":"본문1","en":"...","ko":"..."}},
    {{"label":"본문2","en":"...","ko":"..."}}
 ],
 "hashtags": ["#..","#..","#..","#..","#..","#..","#..","#.."]
}}
- 영업형이면 본문 맨 끝 한 줄에 '{CTA}' 를 붙여도 됩니다(정보형 금지).
"""
    data = safe_json(sys, user)

    st.markdown("## 📝 블로그 패키지 — 제목→본문(≥1500자)→이미지→태그")

    titles = [f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]
    copy_block("① 블로그 제목 복사", "\n".join(titles), 110)

    body = data.get("body","")
    if mode == "sales" and CTA not in body:
        body = body.rstrip() + f"\n\n{CTA}"
    copy_block("② 본문 복사 (≥1500자)", body, 380)

    st.markdown("**③ 이미지 프롬프트 (EN + KO)**")
    for p in data.get("image_prompts", []):
        lbl = p.get("label","이미지")
        copy_block(f"[{lbl}] EN", build_img_en(p.get("en","")), 110)
        copy_block(f"[{lbl}] KO", p.get("ko",""), 90)

    copy_block("④ 해시태그 복사", "\n".join(data.get("hashtags", [])), 100)

# ====== 실행 (버튼 눌렀을 때만) ======
if go:
    try:
        yt_on  = target in ["유튜브 + 블로그","유튜브만"]
        bl_on  = target in ["유튜브 + 블로그","블로그만"]
        if yt_on:  make_youtube()
        if bl_on:  st.markdown("---"); make_blog()
    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 상세를 확인해 주세요.")
        st.exception(e)

st.markdown("---")
st.caption("세이프 부팅 모드: JS/컴포넌트 미사용 · 첫 화면 항상 렌더 · 버튼 실행 방식")
