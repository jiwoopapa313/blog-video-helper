# app.py — 유튜브·블로그 통합 생성기 (Final+Korean Senior Optimized)
# 요구: 환경변수 또는 Streamlit Secrets에 OPENAI_API_KEY 설정

import os, json, time, uuid, html
from datetime import datetime, timezone, timedelta

import streamlit as st
from openai import OpenAI
from streamlit.components.v1 import html as comp_html

# =============================
# 기본 세팅
# =============================
KST = timezone(timedelta(hours=9))
st.set_page_config(page_title="블로그·유튜브 통합 생성기 (Final)", page_icon="🧰", layout="wide")
st.title("🧰 블로그·유튜브 통합 생성기 — Final")
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국 시니어 최적화 · 정보형/영업형 · 복사 버튼 · 이미지 싱크")

CTA = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

# =============================
# OpenAI 클라이언트 & 안전 재시도
# =============================
def _get_client():
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("🔐 OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Secrets 또는 환경변수에 키를 넣어주세요.", icon="⚠️")
    return OpenAI(api_key=api_key) if api_key else None

def _retry(func, *args, **kwargs):
    waits = [0.7, 1.2, 2.2, 3.8]
    err = None
    for i, w in enumerate(waits):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err = e
            if i < len(waits) - 1:
                time.sleep(w)
    if err:
        raise err

def chat_complete(system_prompt: str, user_prompt: str, model: str, temperature: float):
    client = _get_client()
    if not client:
        st.stop()
    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",  "content": user_prompt},
            ],
        )
    resp = _retry(_call)
    return resp.choices[0].message.content.strip()

def safe_json(system_prompt: str, user_prompt: str, model: str, temperature: float):
    raw = chat_complete(system_prompt, user_prompt, model, temperature)
    try:
        return json.loads(raw)
    except Exception:
        raw2 = chat_complete(system_prompt + " RETURN JSON ONLY. NO PROSE.", user_prompt, model, 0.3)
        return json.loads(raw2)

# =============================
# 복사 블록 — 버튼/세이프 모드 지원
# =============================
def copy_block_iframe(title: str, text: str, height: int = 160):
    """안정형: iframe 내부에서만 JS/DOM 동작 → 충돌 최소화"""
    esc_textarea = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_str = f"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans KR', Arial, sans-serif; }}
      .wrap {{ border:1px solid #e5e7eb; border-radius:10px; padding:10px; }}
      .ttl  {{ font-weight:600; margin-bottom:6px; }}
      textarea {{
        width:100%; height:{height}px; border:1px solid #d1d5db; border-radius:8px; padding:8px;
        white-space:pre-wrap; box-sizing:border-box; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      }}
      .row {{ display:flex; gap:8px; align-items:center; margin-top:8px; }}
      .btn {{ padding:6px 10px; border-radius:8px; border:1px solid #d1d5db; cursor:pointer; background:#fff; }}
      small {{ color:#6b7280; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="ttl">{html.escape(title)}</div>
      <textarea readonly id="ta">{esc_textarea}</textarea>
      <div class="row">
        <button class="btn" id="copyBtn">📋 복사</button>
        <small>안 되면 텍스트 클릭 → Ctrl+A → Ctrl+C</small>
      </div>
    </div>
    <script>
      (()=>{
        const btn = document.getElementById("copyBtn");
        const ta  = document.getElementById("ta");
        if (!btn || !ta) return;
        btn.onclick = async () => {{
          try {{
            await navigator.clipboard.writeText(ta.value);
            btn.textContent = "✅ 복사됨";
            setTimeout(()=>btn.textContent="📋 복사", 1200);
          }} catch (e) {{
            try {{
              ta.focus(); ta.select();
              document.execCommand("copy");
              btn.textContent = "✅ 복사됨";
              setTimeout(()=>btn.textContent="📋 복사", 1200);
            }} catch (err) {{
              alert("복사가 차단되었습니다. 텍스트를 직접 선택하여 복사해주세요.");
            }}
          }}
        }}
      }})();
    </script>
  </body>
</html>
"""
    comp_html(html_str, height=height + 110, scrolling=False)

def copy_block_safe(title: str, text: str, height: int = 160):
    """세이프: Streamlit 기본 text_area — 어떤 환경에서도 하얀 화면/DOM 오류 없음"""
    st.markdown(f"**{title}**")
    st.text_area("", text or "", height=height, key="ta_"+uuid.uuid4().hex)
    st.caption("복사: 박스 클릭 → Ctrl+A → Ctrl+C (모바일은 길게 눌러 전체 선택)")

def copy_block(title: str, text: str, height: int = 160, use_button: bool = True):
    if use_button:
        copy_block_iframe(title, text, height)
    else:
        copy_block_safe(title, text, height)

# =============================
# 사이드바(모델/옵션/복사모드)
# =============================
with st.sidebar:
    st.header("⚙️ 생성 설정")
    model_text = st.selectbox("텍스트 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.6, 0.1)
    polish_toggle = st.checkbox("품질 업스케일(4o로 후가공)", value=False)

    st.markdown("---")
    st.markdown("### 🎬 자막/이미지 동기화")
    target_chapter_count = st.selectbox("유튜브 자막(챕터) 개수", [5, 6, 7], index=0)
    include_thumbnail = st.checkbox("썸네일 프롬프트 포함", value=True)

    st.markdown("---")
    st.markdown("### 🖼 이미지 프리셋(한국 시니어)")
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

    st.markdown("---")
    st.markdown("### 📝 블로그 강화 옵션")
    blog_min_chars = st.slider("블로그 최소 길이(자)", 1500, 4000, 2200, 100)
    blog_img_count = st.selectbox("블로그 이미지 프롬프트 개수", [3, 4, 5, 6], index=2)  # 기본 5장

    st.markdown("---")
    st.markdown("### 📋 복사 모드")
    use_copy_button = st.radio("복사 방식을 선택", ["복사 버튼", "세이프(수동 복사)"], index=0) == "복사 버튼"

# =============================
# 한국 시니어 이미지 프리셋 EN 빌더
# =============================
def build_korean_image_prompt(subject_en: str) -> str:
    age_map = {"50대": "in their 50s", "60대": "in their 60s", "70대": "in their 70s"}
    gender_en = {"남성": "Korean man", "여성": "Korean woman"}.get(img_gender, "Korean seniors (men and women)")
    place_map = {
        "한국 가정 거실": "modern Korean home living room interior",
        "한국 아파트 단지": "Korean apartment complex outdoor area",
        "한국 동네 공원": "local Korean neighborhood park",
        "한국 병원/검진센터": "Korean medical clinic or health screening center interior",
        "한국형 주방/식탁": "modern Korean kitchen and dining table",
    }
    shot_map = {"클로즈업":"close-up", "상반신":"medium shot", "전신":"full body shot", "탑뷰/테이블샷":"top view table shot"}
    mood_map = {"따뜻한":"warm", "밝은":"bright", "차분한":"calm", "활기찬":"energetic"}
    style_map= {"사진 실사":"realistic photography, high resolution",
                "시네마틱":"cinematic photo style, soft depth of field",
                "잡지 화보":"editorial magazine style",
                "자연광":"natural lighting, soft daylight"}
    full = (
        f"{gender_en} {age_map.get(img_age,'in their 50s')} at a {place_map.get(img_place,'modern Korean interior')}, "
        f"{shot_map.get(img_shot,'medium shot')}, {mood_map.get(img_mood,'warm')} mood, "
        f"{style_map.get(img_style,'realistic photography, high resolution')}. "
        f"Context: {subject_en}. Korean ethnicity clearly visible, Asian facial features, natural skin tone, "
        "Korean items/signage subtly visible. Avoid Western features."
    )
    return full

# =============================
# 입력 영역
# =============================
st.subheader("🎯 주제 & 유형")
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    topic = st.text_input("주제", value="치매 예방 두뇌 건강법")
with col2:
    tone = st.selectbox("톤/스타일", ["시니어 친화형", "전문가형", "친근한 설명형"], index=0)
with col3:
    mode_sel = st.selectbox("콘텐츠 유형", ["자동 분류", "정보형(블로그 지수)", "시공후기형(영업)"], index=0)
with col4:
    do_both = st.selectbox("생성 대상", ["유튜브 + 블로그", "유튜브만", "블로그만"], index=0)

def simple_classify(text: str) -> str:
    for k in ["시공","교체","설치","수리","누수","보수","후기","현장","관악","강쌤철물"]:
        if k in text: return "sales"
    return "info"

def ensure_mode():
    if mode_sel == "정보형(블로그 지수)": return "info"
    if mode_sel == "시공후기형(영업)":   return "sales"
    return simple_classify(topic)

content_mode = ensure_mode()  # "info" or "sales"
gen = st.button("▶ 모두 생성", type="primary")

# =============================
# 유튜브 생성
# =============================
def generate_youtube(topic, tone, chapters_n, mode, include_thumb):
    sys = (
        "You are a seasoned Korean YouTube scriptwriter for seniors. "
        "Return STRICT JSON only (no prose). Titles must be natural and clickable (no clickbait). "
        "Create EXACTLY N content chapters (2~4 sentences each). "
        "Image prompts MUST depict Korean seniors in Korean settings; provide English prompt and Korean gloss, "
        "and avoid Western features by default."
    )
    user = f"""
[주제] {topic}
[톤] {tone}
[콘텐츠 유형] {"정보형" if mode=="info" else "시공후기형(영업)"}
[N] {chapters_n}

[JSON schema]
{{
  "titles": ["...", "...", "..."],
  "description": "(3~5줄, 시니어 친화, 한국 기준){' (마지막 줄 CTA: ' + CTA + ')' if mode=='sales' else ''}",
  "chapters": [
     {{"title":"Tip1","script":"... (2~4문장)"}},
     {{"title":"Tip2","script":"... (2~4문장)"}},
     {{"title":"Tip3","script":"... (2~4문장)"}},
     {{"title":"Tip4","script":"... (2~4문장)"}},
     {{"title":"Tip5","script":"... (2~4문장)"}}
  ],
  "image_prompts": [
     {{"label":"Chap1","en":"...","ko":"..."}},
     {{"label":"Chap2","en":"...","ko":"..."}},
     {{"label":"Chap3","en":"...","ko":"..."}},
     {{"label":"Chap4","en":"...","ko":"..."}},
     {{"label":"Chap5","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#..", "#..", "#..", "#.."]
}}
- 'chapters'와 'image_prompts'는 개수 N으로 맞추고, 인덱스 1:1 매칭.
- 정보형은 CTA 금지, 영업형은 설명 마지막 줄에 CTA 허용.
"""
    data = safe_json(sys, user, model_text, temperature)

    # 개수/정합성 보정
    chapters = data.get("chapters", [])[:chapters_n]
    prompts  = data.get("image_prompts", [])[:chapters_n]
    while len(chapters) < chapters_n:
        chapters.append({"title": f"Tip{len(chapters)+1}", "script": "간단한 보충 설명을 제공합니다."})
    while len(prompts) < chapters_n:
        i = len(prompts)
        prompts.append({"label": f"Chap{i+1}", "en": f"Visual support for chapter {i+1} of '{topic}'", "ko": f"챕터 {i+1} 보조 이미지"})
    data["chapters"] = chapters
    data["image_prompts"] = prompts

    # 업스케일(선택)
    if polish_toggle:
        sys_p = "Polish Korean text for clarity; keep JSON shape and counts. Return JSON only."
        try:
            polished = chat_complete(sys_p, json.dumps(data, ensure_ascii=False), "gpt-4o", 0.4)
            data = json.loads(polished)
        except Exception:
            pass

    # 영업형: 설명 끝 CTA 보장
    if content_mode == "sales":
        desc = data.get("description","").rstrip()
        if CTA not in desc:
            data["description"] = (desc + f"\n{CTA}").strip()

    return data

# =============================
# 블로그 생성 (강화판)
# =============================
def generate_blog(topic, tone, mode, min_chars: int, img_count: int):
    """
    - 본문 길이: min_chars 이상(기본 2200자)
    - 섹션: 서론 / 핵심 5가지 / 체크리스트(6~8) / 자가진단(5) / FAQ(3) / 마무리
    - 이미지 프롬프트: img_count개 (대표 1 + 본문 1..N-1)
    - [이미지: ...] 마커 3~5곳 자동 요구
    """
    sys = (
        "You are a Korean Naver-SEO writer. Return STRICT JSON only (no prose). "
        "Senior-friendly tone; short paragraphs; bullet lists. "
        "Body MUST be >= {min_chars} Korean characters and include 3~5 '[이미지: ...]' markers. "
        "Add rich sections: 서론, 핵심 5가지(번호 리스트), 체크리스트(체크박스 느낌 6~8), 자가진단 5문항(예/아니오), "
        "자주 묻는 질문 3개(질문/답변), 마무리 요약. "
        "If '정보형' then NEVER include phone CTA. If '영업형', allow one-line CTA at the very end."
    ).format(min_chars=min_chars)

    img_items = [{"label": "대표", "en": "...", "ko": "..."}] + [
        {"label": f"본문{i}", "en": "...", "ko": "..."} for i in range(1, img_count)
    ]

    user = f"""
[주제] {topic}
[톤] {tone}
[콘텐츠 유형] {"정보형" if mode=="info" else "시공후기형(영업)"}
[최소길이] {min_chars}자 이상
[이미지 프롬프트 개수] {img_count}개 (대표 1 + 본문 {img_count-1})

[JSON schema]
{{
  "titles": ["...", "...", "..."],
  "body": "(서론→핵심5가지→체크리스트→자가진단5→FAQ3→마무리, 전체 {min_chars}+자, [이미지: ...] 3~5곳)",
  "image_prompts": {json.dumps(img_items, ensure_ascii=False)},
  "hashtags": ["#..", "#..", "#..", "#..", "#..", "#..", "#..", "#.."]
}}
- Use clear headings like '### 서론', '### 핵심 5가지', '### 체크리스트', '### 자가진단', '### 자주 묻는 질문(FAQ)', '### 마무리'.
- Insert [이미지: ...] markers at natural breakpoints (서론 후, 핵심 중간, 결론 앞 등).
"""
    data = safe_json(sys, user, model_text, temperature)

    # 길이 보정 루프
    body = data.get("body", "")
    if len(body) < min_chars:
        sys_len = (
            "Expand the SAME structure to >= {target} Korean characters, preserve headings and 3~5 [이미지: ...] markers. "
            "Return JSON only, same fields."
        ).format(target=min_chars + 300)
        try:
            raw2 = chat_complete(sys_len, json.dumps(data, ensure_ascii=False), model_text, 0.5)
            data2 = json.loads(raw2)
            body = data2.get("body", body)
            data = data2
        except Exception:
            pass

    # 업스케일(선택)
    if polish_toggle:
        sys_p = "Polish Korean writing for clarity and flow. Keep JSON structure and counts."
        try:
            polished = chat_complete(sys_p, json.dumps(data, ensure_ascii=False), "gpt-4o", 0.4)
            data = json.loads(polished)
        except Exception:
            pass

    # CTA 처리
    body = data.get("body", "")
    if mode == "sales" and CTA not in body:
        data["body"] = body.rstrip() + f"\n\n{CTA}"
    if mode == "info" and CTA in body:
        data["body"] = body.replace(CTA, "").strip()

    # 이미지 프롬프트 개수 보정
    prompts = data.get("image_prompts", [])[:img_count]
    while len(prompts) < img_count:
        idx = len(prompts)
        if idx == 0:
            prompts.append({"label":"대표","en":f"Key visual for '{topic}'","ko":"대표 이미지 설명"})
        else:
            prompts.append({"label":f"본문{idx}","en":f"Supporting visual for section {idx} of '{topic}'","ko":f"본문 섹션 {idx} 보조 이미지"})
    data["image_prompts"] = prompts

    return data

# =============================
# 실행
# =============================
if gen:
    try:
        do_yt = do_both in ["유튜브 + 블로그", "유튜브만"]
        do_blog = do_both in ["유튜브 + 블로그", "블로그만"]

        # ---------- 유튜브 ----------
        if do_yt:
            st.markdown("## 📺 유튜브 패키지 — 제목→설명→자막→이미지→태그")
            yt = generate_youtube(topic, tone, target_chapter_count, content_mode, include_thumbnail)

            # ① 제목
            st.markdown("**① 영상 제목 3개**")
            titles = [f"{i+1}. {t}" for i, t in enumerate(yt.get("titles", [])[:3])]
            copy_block("영상 제목 복사", "\n".join(titles), 110, use_button=use_copy_button)

            # ② 설명
            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", yt.get("description",""), 160, use_button=use_copy_button)

            # ③ 브루 자막
            st.markdown("**③ 브루 자막 (챕터별 복사 + 전체 복사)**")
            chapters = yt.get("chapters", [])[:target_chapter_count]
            all_lines = []
            for idx, ch in enumerate(chapters, start=1):
                title = ch.get("title", f"챕터 {idx}")
                script = ch.get("script", "")
                all_lines.append(script)
                copy_block(f"[챕터 {idx}] {title}", script, 140, use_button=use_copy_button)
            copy_block("브루 자막 — 전체 일괄 복사", "\n\n".join(all_lines), 220, use_button=use_copy_button)

            # ④ 이미지 프롬프트 (자막과 동일 개수)
            st.markdown("**④ 이미지 프롬프트 (EN + KO) — 자막과 동일 개수**")
            if include_thumbnail:
                copy_block(
                    "[썸네일] EN (Korean preset enforced)",
                    build_korean_image_prompt(f"YouTube thumbnail for topic: {topic}. Clear space for big Korean title text, high contrast."),
                    110, use_button=use_copy_button
                )
                copy_block(
                    "[썸네일] KO",
                    f"{img_age} {img_gender} 한국인이 {img_place}에서 {img_mood} 분위기, {img_style} {img_shot} — 한글 큰 제목 영역 확보, 고대비",
                    90, use_button=use_copy_button
                )

            base_prompts = yt.get("image_prompts", [])[:target_chapter_count]
            while len(base_prompts) < len(chapters):
                i = len(base_prompts)
                base_prompts.append({"label": f"Chap{i+1}", "en": f"Visual support for chapter {i+1}", "ko": f"챕터 {i+1} 보조 이미지"})
            for idx, p in enumerate(base_prompts, start=1):
                base_en = p.get("en","")
                enforced_en = build_korean_image_prompt(base_en)
                ko_desc = p.get("ko","") or f"{img_age} {img_gender} 한국인이 {img_place}에서 '{chapters[idx-1].get('title','챕터')}' 내용을 표현, {img_mood} 분위기, {img_style} {img_shot}"
                copy_block(f"[챕터 {idx}] EN (Korean preset enforced)", enforced_en, 110, use_button=use_copy_button)
                copy_block(f"[챕터 {idx}] KO", ko_desc, 90, use_button=use_copy_button)

            # ⑤ 해시태그
            st.markdown("**⑤ 해시태그 (마지막)**")
            copy_block("해시태그 복사", " ".join(yt.get("hashtags", [])), 80, use_button=use_copy_button)

        # ---------- 블로그 ----------
        if do_blog:
            st.markdown("---")
            st.markdown("## 📝 블로그 패키지 — 제목→본문(강화)→이미지→태그")
            blog = generate_blog(topic, tone, content_mode, blog_min_chars, blog_img_count)

            # ① 제목
            st.markdown("**① 블로그 제목 3개 (SEO)**")
            b_titles = [f"{i+1}. {t}" for i, t in enumerate(blog.get("titles", [])[:3])]
            copy_block("블로그 제목 복사", "\n".join(b_titles), 110, use_button=use_copy_button)

            # ② 본문(강화: 2200자+, 섹션/체크리스트/자가진단/FAQ 포함)
            st.markdown("**② 본문 (≥설정값, 강화 구성 포함)**")
            copy_block("블로그 본문 복사", blog.get("body",""), 420, use_button=use_copy_button)

            # ③ 이미지 프롬프트 (EN + KO) — 선택 수(blog_img_count) 출력, EN은 한국 프리셋으로 재조합
            st.markdown("**③ 이미지 프롬프트 (EN + KO)**")
            for p in blog.get("image_prompts", [])[:blog_img_count]:
                lbl = p.get("label", "이미지")
                copy_block(f"[{lbl}] EN (Korean preset enforced)", build_korean_image_prompt(p.get("en","")), 110, use_button=use_copy_button)
                copy_block(f"[{lbl}] KO", p.get("ko",""), 90, use_button=use_copy_button)

            # ④ 해시태그
            st.markdown("**④ 해시태그 (마지막)**")
            copy_block("블로그 태그 복사", "\n".join(blog.get("hashtags", [])), 100, use_button=use_copy_button)

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 상세를 확인해 주세요.")
        st.exception(e)

st.markdown("---")
st.caption("정보형은 CTA 자동 제거, 시공후기형(영업)은 CTA 자동 삽입. 자막↔이미지 1:1 동기화, 한국 시니어 프리셋 강제.")
