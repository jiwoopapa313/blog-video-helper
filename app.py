# app.py — 블로그·유튜브 통합 생성기 (Pro + Korean Image Preset)
# 요구: Streamlit Secrets 또는 환경변수에 OPENAI_API_KEY 설정

import os, time, json, uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# =============================
# 기본 세팅
# =============================
KST = timezone(timedelta(hours=9))
st.set_page_config(page_title="블로그·유튜브 통합 생성기 (Pro)", page_icon="🧰", layout="wide")
st.title("🧰 블로그·유튜브 통합 생성기 — Pro 버전")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 고품질 생성 + 복사 버튼 + 이미지 프롬프트(한국 시니어 프리셋)")

# =============================
# OpenAI 클라이언트 & 안전 재시도
# =============================
def _get_client():
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Secrets에 키를 넣어주세요.")
    return OpenAI(api_key=api_key)

def _retry(func, *args, **kwargs):
    backoff = [0.7, 1.2, 2.5, 4.0]
    last_err = None
    for i, wait in enumerate(backoff):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            if i < len(backoff) - 1:
                time.sleep(wait)
            else:
                raise last_err

def chat_complete(system_prompt: str, user_prompt: str, model: str, temperature: float):
    client = _get_client()
    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    resp = _retry(_call)
    return resp.choices[0].message.content.strip()

# =============================
# UI 유틸: 복사 가능한 블록
# =============================
def copy_block(title: str, text: str, height: int = 160):
    tid = "ta" + str(uuid.uuid4()).replace("-", "")
    esc = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    comp_html(
        f"""
        <div style='border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin:8px 0;'>
          <div style='font-weight:600;margin-bottom:6px'>{title}</div>
          <textarea id='{tid}' style='width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;'>{esc}</textarea>
          <button onclick="navigator.clipboard.writeText(document.getElementById('{tid}').value)"
                  style='margin-top:8px;padding:6px 10px;border-radius:8px;border:1px solid #d1d5db;cursor:pointer;'>
            📋 복사
          </button>
        </div>
        """,
        height=height + 110,
    )

# =============================
# 한국 시니어 이미지 프리셋
# =============================
with st.sidebar:
    st.header("⚙️ 생성 설정")
    st.info("※ Streamlit Secrets에 OPENAI_API_KEY만 넣으면 됩니다.", icon="🔐")
    model_text = st.selectbox("텍스트 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.6, 0.1)
    polish_toggle = st.checkbox("품질 업스케일(4o로 후가공)", value=False)

    with st.expander("🖼 이미지 프리셋(한국 시니어)", expanded=True):
        img_age = st.selectbox("연령대", ["50대", "60대", "70대"], index=0)
        img_gender = st.selectbox("성별", ["혼합", "남성", "여성"], index=0)
        img_place = st.selectbox(
            "장소/배경",
            ["한국 가정 거실", "한국 아파트 단지", "한국 동네 공원", "한국 병원/검진센터", "한국형 주방/식탁"],
            index=0,
        )
        img_mood = st.selectbox("무드", ["따뜻한", "밝은", "차분한", "활기찬"], index=0)
        img_shot = st.selectbox("샷 타입", ["클로즈업", "상반신", "전신", "탑뷰/테이블샷"], index=1)
        img_style = st.selectbox("스타일", ["사진 실사", "시네마틱", "잡지 화보", "자연광"], index=0)

def build_korean_image_prompt(
    subject_en: str,
    age_str: str,
    gender: str,
    place: str,
    mood: str,
    shot: str,
    style: str,
) -> str:
    age_map = {"50대": "in their 50s", "60대": "in their 60s", "70대": "in their 70s"}
    age_en = age_map.get(age_str, "in their 50s")

    if gender == "남성":
        gender_en = "Korean man"
    elif gender == "여성":
        gender_en = "Korean woman"
    else:
        gender_en = "Korean seniors (men and women)"

    place_map = {
        "한국 가정 거실": "modern Korean home living room interior",
        "한국 아파트 단지": "Korean apartment complex outdoor area",
        "한국 동네 공원": "local Korean neighborhood park",
        "한국 병원/검진센터": "Korean medical clinic or health screening center interior",
        "한국형 주방/식탁": "modern Korean kitchen and dining table",
    }
    place_en = place_map.get(place, "modern Korean home interior")

    shot_map = {"클로즈업": "close-up", "상반신": "medium shot", "전신": "full body shot", "탑뷰/테이블샷": "top view table shot"}
    shot_en = shot_map.get(shot, "medium shot")

    mood_en = {"따뜻한": "warm", "밝은": "bright", "차분한": "calm", "활기찬": "energetic"}.get(mood, "warm")
    style_en = {
        "사진 실사": "realistic photography, high resolution",
        "시네마틱": "cinematic photo style, soft depth of field",
        "잡지 화보": "editorial magazine style",
        "자연광": "natural lighting, soft daylight",
    }.get(style, "realistic photography, high resolution")

    negative = "avoid Western facial features, avoid Caucasian, avoid blond hair, avoid blue eyes"

    full = (
        f"{gender_en} {age_en} at a {place_en}, {shot_en}, {mood_en} mood, {style_en}. "
        f"Context: {subject_en}. "
        "Korean ethnicity clearly visible, Asian facial features, natural skin tone, Korean signage or items subtly visible. "
        f"{negative}"
    )
    return full

# =============================
# 입력 영역
# =============================
st.subheader("🎯 주제 & 타깃")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    topic = st.text_input("주제", value="치매 예방 두뇌 건강법")
with col2:
    audience = st.selectbox("타깃", ["50~70대 시니어", "30~50대 주부", "일반 성인"], index=0)
with col3:
    tone = st.selectbox("톤/스타일", ["시니어 친화형", "전문가형", "친근한 설명형"], index=0)

colA, colB = st.columns(2)

# =============================
# 유튜브 생성
# =============================
with colA:
    st.markdown("### 📺 유튜브 패키지 — 제목→설명→자막→이미지→태그")
    if st.button("▶ 유튜브 생성", type="primary"):
        try:
            sys = (
                "You are a seasoned Korean YouTube scriptwriter for seniors. "
                "Return STRICT JSON only (no prose). Titles must be natural and clickable (no clickbait). "
                "Chapters are Vrew-friendly: 2~4 sentences each. "
                "Image prompts MUST depict Korean seniors in Korean settings (homes, parks, clinics), "
                "include 'Korean/Asian' ethnicity, and avoid Western features by default. "
                "Include English prompt and Korean gloss for image prompts."
            )
            user = f"""
[주제] {topic}
[타깃] {audience}
[톤] {tone}

Return JSON with this schema:
{{
  "titles": ["...", "...", "..."],
  "description": "(3~5줄)",
  "chapters": [
     {{"title":"인트로","script":"..."}},
     {{"title":"Tip1","script":"..."}},
     {{"title":"Tip2","script":"..."}},
     {{"title":"Tip3","script":"..."}},
     {{"title":"Tip4","script":"..."}},
     {{"title":"Tip5","script":"..."}},
     {{"title":"엔딩","script":"..."}}
  ],
  "image_prompts": [
     {{"label":"썸네일","en":"...","ko":"..."}},
     {{"label":"본문1","en":"...","ko":"..."}},
     {{"label":"본문2","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#..", "#..", "#.."]
}}
- Constraints:
  1) Put titles first. 2) Hashtags at the end. 3) Practical, trustworthy advice for Korean seniors.
"""
            raw = chat_complete(sys, user, model_text, temperature)
            try:
                data = json.loads(raw)
            except Exception:
                sys2 = sys + " Return ONLY compact JSON without prose."
                raw = chat_complete(sys2, user, model_text, temperature)
                data = json.loads(raw)

            # 업스케일(선택)
            if polish_toggle:
                sys_p = "Polish the Korean text for dignity and clarity, keep the same structure, return JSON only."
                polished = chat_complete(sys_p, json.dumps(data, ensure_ascii=False), "gpt-4o", 0.4)
                try:
                    data = json.loads(polished)
                except Exception:
                    pass

            # ① 제목
            st.markdown("**① 영상 제목 3개**")
            yt_titles = [f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]
            copy_block("영상 제목 복사", "\n".join(yt_titles), 110)

            # ② 설명
            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", data.get("description", ""), 160)

            # ③ 브루 자막
            st.markdown("**③ 브루 자막 (챕터별 복사 + 전체 복사)**")
            chapters = data.get("chapters", [])
            all_lines = []
            for ch in chapters:
                title = ch.get("title", "챕터")
                script = ch.get("script", "")
                all_lines.append(script)
                copy_block(f"[{title}] 자막", script, 140)
            copy_block("브루 자막 — 전체 일괄 복사", "\n\n".join(all_lines), 220)

            # ④ 이미지 프롬프트 (한국 프리셋 강제 적용)
            st.markdown("**④ 이미지 프롬프트 (EN + KO)**")
            for p in data.get("image_prompts", []):
                lbl = p.get("label", "이미지")
                base_en = p.get("en", "")
                enforced_en = build_korean_image_prompt(
                    subject_en=base_en,
                    age_str=img_age,
                    gender=img_gender,
                    place=img_place,
                    mood=img_mood,
                    shot=img_shot,
                    style=img_style,
                )
                ko_desc = p.get("ko", "") or f"{img_age} {img_gender} 한국인이 {img_place}에서 {img_mood} 분위기로 촬영된 {img_style} {img_shot} 장면"
                copy_block(f"[{lbl}] EN (Korean preset enforced)", enforced_en, 110)
                copy_block(f"[{lbl}] KO", ko_desc, 90)

            # ⑤ 해시태그 (마지막)
            st.markdown("**⑤ 해시태그 (마지막)**")
            tags = " ".join(data.get("hashtags", []))
            copy_block("해시태그 복사", tags, 80)

        except Exception as e:
            st.error(f"유튜브 생성 오류: {e}")

# =============================
# 블로그 생성 (≥1500자)
# =============================
with colB:
    st.markdown("### ✍️ 블로그 패키지 — 제목→본문(≥1500자)→이미지→태그")
    if st.button("▶ 블로그 생성", type="primary"):
        try:
            sys = (
                "You are a Korean Naver-SEO writer. Return STRICT JSON only (no prose). "
                "Body must be >= 1500 Korean characters with short paragraphs and lists. "
                "Image prompts MUST depict Korean seniors in Korean settings (homes, parks, clinics), "
                "include 'Korean/Asian' ethnicity, and avoid Western features by default. "
                "Include English prompt and Korean gloss for image prompts."
            )
            user = f"""
[주제] {topic}
[타깃] {audience}
[톤] {tone}

Return JSON with this schema:
{{
  "titles": ["...", "...", "..."],
  "body": "(>=1500자 한국어 본문)",
  "image_prompts": [
     {{"label":"대표","en":"...","ko":"..."}},
     {{"label":"본문1","en":"...","ko":"..."}},
     {{"label":"본문2","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#..", "#.."]
}}
- Constraints: titles first; hashtags last; no phone CTA for info posts; friendly senior tone; include [이미지: ...] markers 2~3 places.
"""
            raw = chat_complete(sys, user, model_text, temperature)
            try:
                data = json.loads(raw)
            except Exception:
                sys2 = sys + " Return ONLY compact JSON without prose."
                raw = chat_complete(sys2, user, model_text, temperature)
                data = json.loads(raw)

            body = data.get("body", "")

            # 길이 보정(최소 1500자)
            if len(body) < 1500:
                sys_len = "Expand to >= 1700 Korean characters while keeping structure and headings. Return JSON only with same fields."
                raw2 = chat_complete(sys_len, json.dumps(data, ensure_ascii=False), model_text, 0.5)
                try:
                    data2 = json.loads(raw2)
                    body = data2.get("body", body)
                    data = data2
                except Exception:
                    pass

            # 업스케일(선택)
            if polish_toggle:
                sys_p = "Polish Korean writing for clarity and flow. Keep JSON structure."
                polished = chat_complete(sys_p, json.dumps(data, ensure_ascii=False), "gpt-4o", 0.4)
                try:
                    data = json.loads(polished)
                    body = data.get("body", body)
                except Exception:
                    pass

            # ① 제목
            st.markdown("**① 블로그 제목 3개**")
            blog_titles = [f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]
            copy_block("블로그 제목 복사", "\n".join(blog_titles), 110)

            # ② 본문
            st.markdown("**② 본문 (≥1500자)**")
            copy_block("블로그 본문 복사", body, 360)

            # ③ 이미지 프롬프트 (한국 프리셋 강제 적용)
            st.markdown("**③ 이미지 프롬프트 (EN + KO)**")
            for p in data.get("image_prompts", []):
                lbl = p.get("label", "이미지")
                base_en = p.get("en", "")
                enforced_en = build_korean_image_prompt(
                    subject_en=base_en,
                    age_str=img_age,
                    gender=img_gender,
                    place=img_place,
                    mood=img_mood,
                    shot=img_shot,
                    style=img_style,
                )
                ko_desc = p.get("ko", "") or f"{img_age} {img_gender} 한국인이 {img_place}에서 {img_mood} 분위기로 촬영된 {img_style} {img_shot} 장면"
                copy_block(f"[{lbl}] EN (Korean preset enforced)", enforced_en, 110)
                copy_block(f"[{lbl}] KO", ko_desc, 90)

            # ④ 해시태그 (마지막)
            st.markdown("**④ 해시태그 (마지막)**")
            tags = "\n".join(data.get("hashtags", []))
            copy_block("블로그 태그 복사", tags, 100)

        except Exception as e:
            st.error(f"블로그 생성 오류: {e}")

st.markdown("---")
st.caption("※ 더 말맛이 필요하면 사이드바의 '품질 업스케일(4o로 후가공)'을 켜세요. 호출량이 늘 수 있습니다.")
