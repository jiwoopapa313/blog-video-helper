import os, time, base64
from datetime import datetime, timezone, timedelta
import streamlit as st
from openai import OpenAI

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="블로그·영상 통합 도우미", page_icon="🧰", layout="wide")
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
st.title("🧰 블로그·영상 통합 도우미")
st.caption(f"KST 기준 현재 시각: {now_kst} · 한 번에 블로그/숏츠/이미지 생성")

# -----------------------------
# 공통 사이드바
# -----------------------------
with st.sidebar:
    st.header("⚙️ 공통 설정")
    st.info("※ Streamlit Cloud의 Secrets에 OPENAI_API_KEY만 넣으면, 여기서는 입력할 필요 없습니다.", icon="🔐")
    model_text = st.selectbox("텍스트 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    model_image = st.selectbox("이미지 모델", ["gpt-image-1"], index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.6, 0.1)
    # 포맷팅 옵션(옵션 5)
    short_paragraphs = st.checkbox("짧은 문단(가독성 향상)", value=True)
    emoji_level = st.slider("이모지 사용량(0=없음)", 0, 3, 1)
    # 쿠팡 파트너스 기본값(옵션 4)
    default_coupang = st.checkbox("쿠팡 파트너스 고지 기본 사용", value=False)

# -----------------------------
# OpenAI 클라이언트 & 안전 재시도(옵션 1)
# -----------------------------

def _get_client():
    api_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Cloud의 Secrets에 OPENAI_API_KEY를 넣어주세요.", icon="⚠️")
    return OpenAI(api_key=api_key)


def _retry(func, *args, **kwargs):
    backoffs = [0, 1, 2, 4]
    last_err = None
    for i, wait in enumerate(backoffs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            if i < len(backoffs) - 1:
                time.sleep(wait)
            else:
                raise last_err


def chat_complete(system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
    client = _get_client()
    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        )
    resp = _retry(_call)
    return resp.choices[0].message.content.strip()


def generate_image(prompt: str, size: str, model: str) -> bytes:
    client = _get_client()
    def _call():
        return client.images.generate(model=model, prompt=prompt, size=size)
    img = _retry(_call)
    return base64.b64decode(img.data[0].b64_json)

# -----------------------------
# 탭 구성 (요청: 사업계획 카테고리 삭제)
# -----------------------------

tab2, tab3, tab4, tab5 = st.tabs([
    "🛒 상품 URL → 콘텐츠",
    "📝 블로그 SEO",
    "🖼️ 썸네일/이미지",
    "📦 카테고리 자동화(베타)",
])

# -----------------------------
# 탭2: 상품 URL → 콘텐츠 (옵션 4 적용)
# -----------------------------
with tab2:
    st.subheader("🛒 상품 URL → 상세페이지/숏츠/블로그 한 번에")
    url = st.text_input("상품 URL(쿠팡/스마트스토어 등)")
    tone = st.selectbox("톤/스타일", ["작업자 시선·쉬운 말투(기본)", "전문가형", "세일즈형(자극)"], index=0)
    include_coupang = st.checkbox("쿠팡파트너스 고지 문구 포함", value=default_coupang)
    local_tags = "#관악구철물점 #관악구집수리 #서초구집수리 #동작구집수리 #전기설비 #수도설비 #전등교체 #수전교체 #수도꼭지"

    if st.button("콘텐츠 생성", type="primary"):
        style_note = "작업자 시선 + 쉬운 말투" if tone.startswith("작업자") else tone
        disclaimer = "※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다." if include_coupang else ""
        format_note = f"\n[문단] {'짧게' if short_paragraphs else '자유'} / [이모지] {emoji_level}단계"
        sys = (
            "당신은 한국 이커머스 상세/블로그/숏츠 제작자입니다. 사실 위주, 허위 과장 금지. "
            "출력: 1) 상세 개요 2) 스펙/장점 표 3) 구매 전 체크리스트 "
            "4) 40초 숏츠 대본(6~7줄, 마지막 멘트: '지금 프로필을 클릭하시고, 제품을 확인하세요!') "
            "5) 네이버 블로그 본문(이미지 위치 [이미지: ...]) 6) 해시태그 두 형식(한 줄/줄바꿈) 7) 주의사항."
        )
        user = f"""
[상품URL] {url}
[스타일] {style_note}
[지역 해시태그] {local_tags}
[쿠팡파트너스 문구] {disclaimer}
{format_note}
"""
        with st.spinner("생성 중..."):
            txt = chat_complete(sys, user, model_text, temperature)
        st.success("완료")
        st.text_area("미리보기", txt, height=420)
        st.download_button("📝 저장 (product_content.txt)", txt, file_name="product_content.txt")
        st.download_button("📝 저장 (product_content.md)", txt, file_name="product_content.md")

# -----------------------------
# 탭3: 블로그 SEO (옵션 5 적용)
# -----------------------------
with tab3:
    st.subheader("📝 네이버 블로그 최적화 글")
    topic = st.text_input("주제/키워드", placeholder="예: 양재동 건강식품 매장 LED 안정기 수리 현장")
    must_tags = st.text_area("항상 포함할 해시태그(본문꾸미기용)", value="#관악구철물점 #관악구집수리 #서초구집수리 #동작구집수리 #전기설비 #수도설비 #전등교체 #수전교체 #수도꼭지", height=80)
    length = st.selectbox("길이", ["1000~1500자", "1500~2000자", "2000자 이상"], index=1)

    if st.button("블로그 글 생성", type="primary"):
        format_note = f"\n[문단] {'짧게' if short_paragraphs else '자유'} / [이모지] {emoji_level}단계"
        sys = ("당신은 네이버 블로그 상위노출 글 작성자입니다. "
               "요구: 쉬운 말투, 리스트 중심, 지역키워드 자연 반복, 120자 메타설명, CTA 포함(정보성 제외), 이미지 위치 표기, "
               "끝에 해시태그 두 형식(한 줄/줄바꿈).")
        user = f"""
[주제] {topic}
[길이] {length}
[항상 포함할 태그] {must_tags}
[지역 기본값] 관악구·서초구·동작구
{format_note}
"""
        with st.spinner("생성 중..."):
            txt = chat_complete(sys, user, model_text, temperature)
        st.success("완료")
        st.text_area("미리보기", txt, height=420)
        st.download_button("📝 저장 (naver_blog.txt)", txt, file_name="naver_blog.txt")
        st.download_button("📝 저장 (naver_blog.md)", txt, file_name="naver_blog.md")

# -----------------------------
# 탭4: 썸네일/이미지 (요청 시에만)
# -----------------------------
with tab4:
    st.subheader("🖼️ 썸네일/이미지 자동 생성 (사용자 요청 시에만)")
    st.info("대표님 요청하실 때만 이미지 생성 버튼을 누르세요.")
    prompt = st.text_area("이미지 프롬프트(영문 권장)", value=(
        "A clean, modern Korean home interior, Korean hands installing LED edge light; "
        "bold Korean title text '혈압 잡는 스트레칭 3가지' at top; high contrast; thumbnail framing; "
        "avoid extra small text; suitable for YouTube thumbnail; 16:9; Korean Hangul high legibility, large bold text"
    ), height=120)
    size = st.selectbox("사이즈", ["1024x1024", "1024x1792", "1792x1024"], index=0)

    if st.button("이미지 생성", type="primary"):
        try:
            with st.spinner("이미지 생성 중..."):
                png_bytes = generate_image(prompt, size=size, model=model_image)
            st.success("완료")
            st.image(png_bytes, caption="생성된 미리보기")
            st.download_button("🖼️ 다운로드 (thumbnail.png)", png_bytes, file_name="thumbnail.png")
            st.info("한글 가독성이 떨어지면 프롬프트 끝에 'Korean Hangul big bold text'를 덧붙이세요.")
        except Exception as e:
            st.error(f"이미지 생성 실패: {e}")
            st.caption("OPENAI_API_KEY / 모델명 / 사용량 한도 등을 확인하세요.")

# -----------------------------
# 탭5: 카테고리 자동화(베타) — 옵션 2·3·5 모두 적용
# -----------------------------
with tab5:
    st.subheader("📦 카테고리 자동화 — 시공후기/정보제공에 따라 CTA 자동 처리")

    # 프리셋(옵션 3)
    preset_col1, preset_col2, preset_col3 = st.columns(3)
    if preset_col1.button("프리셋: 50대 이후 조심해야 할 운동"):
        st.session_state["preset_topic"] = "50대 이후 조심해야 할 운동"
    if preset_col2.button("프리셋: 치매 예방 두뇌 건강법"):
        st.session_state["preset_topic"] = "치매 예방 두뇌 건강법"
    if preset_col3.button("프리셋: 겨울철 보일러 관리법"):
        st.session_state["preset_topic"] = "겨울철 보일러 관리법"

    colA, colB, colC = st.columns(3)
    with colA:
        category = st.radio("카테고리", ["시공후기", "정보제공", "혼합형"], index=1)
    with colB:
        topic5 = st.text_input("주제", value=st.session_state.get("preset_topic", "치매 예방 두뇌 건강법"))
    with colC:
        audience = st.selectbox("타깃", ["50~70대 시니어", "30~50대 주부", "일반 성인"], index=0)

    def _cta_for(cat: str) -> str:
        if cat == "시공후기":
            return "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"
        if cat == "혼합형":
            return "궁금한 점은 댓글이나 연락 주시면 빠르게 도와드리겠습니다. (상담문의: 010-2276-8163)"
        return ""  # 정보제공은 CTA 제거

    format_note = f"[문단] {'짧게' if short_paragraphs else '자유'} / [이모지] {emoji_level}단계"

    # 유튜브 패키지
    if st.button("▶ 유튜브 패키지 생성"):
        sys_y = (
            "You are a Korean creator for YouTube. Use concise, friendly Korean. "
            "Avoid exaggeration. 정보제공일 때는 상담 멘트를 넣지 말 것."
        )
        user_y = f"""
[주제] {topic5}
[카테고리] {category}
[타깃] {audience}
{format_note}
[요구 산출물]
1) 유튜브 제목 3개(클릭률 최적화)
2) 영상 설명문(SEO)
3) 브루 자막용 스크립트(60초)
4) 해시태그 10개
정보제공일 경우 상담 멘트 금지
"""
        with st.spinner("생성 중…"):
            yt_txt = chat_complete(sys_y, user_y, model_text, temperature)
        if category == "정보제공":
            yt_txt = yt_txt.replace("강쌤철물", "").replace("010-2276-8163", "").strip()
        st.success("유튜브 패키지 생성 완료")
        st.text_area("YouTube Package", yt_txt, height=420)
        st.download_button("⬇️ YouTube_Package.txt", yt_txt, file_name="YouTube_Package.txt")
        st.download_button("⬇️ YouTube_Package.md", yt_txt, file_name="YouTube_Package.md")

    # 블로그 패키지
    if st.button("▶ 블로그 패키지 생성"):
        sys_b = (
            "You write Naver-SEO-optimized posts in Korean. Keep paragraphs short, use lists, insert [이미지: 설명] 3곳, "
            "표 1개(비교표/체크리스트), 끝에 해시태그 두 형식(한 줄/줄바꿈). 정보제공이면 상담 멘트를 절대 넣지 말고, "
            "부드러운 마무리 문장으로 끝낼 것."
        )
        user_b = f"""
[주제] {topic5}
[카테고리] {category}
{format_note}
[요구 산출물]
1) 제목 3개(네이버 최적화)
2) 본문 1500~2000자
3) [이미지: ...] 위치 3곳
4) 표 1개(비교표나 체크리스트)
5) 해시태그(한 줄/줄바꿈)
"""
        with st.spinner("생성 중…"):
            blog_txt = chat_complete(sys_b, user_b, model_text, temperature)
        cta = _cta_for(category)
        if category == "정보제공":
            blog_txt = blog_txt.replace("강쌤철물", "").replace("010-2276-8163", "").strip()
            blog_txt += "\n\n[마무리] 작은 습관이 건강을 지키는 큰 힘이 됩니다. 오늘부터 실천해 보세요."
        else:
            if cta:
                blog_txt += f"\n\n[상담 안내] {cta}"
        st.success("블로그 패키지 생성 완료")
        st.text_area("Blog Package", blog_txt, height=500)
        st.download_button("⬇️ Blog_Package.txt", blog_txt, file_name="Blog_Package.txt")
        st.download_button("⬇️ Blog_Package.md", blog_txt, file_name="Blog_Package.md")

st.caption("※ 이미지 생성은 대표님이 원하실 때만 3번 탭에서 실행하세요. (자동 생성 안 함)")

# =============================
# 🎬 유튜브·블로그 통합 (복사버튼) — 추가 섹션
# =============================
try:
    import json, uuid
    from streamlit.components.v1 import html as comp_html

    st.markdown("---")
    st.header("🎬 유튜브·블로그 통합 생성 — 제목 우선 · 태그 마지막 · 복사버튼")

    def copy_block(title: str, text: str, height: int = 140):
        key = str(uuid.uuid4()).replace('-', '')
        comp_html(f"""
        <div style='border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin:8px 0'>
          <div style='font-weight:600;margin-bottom:6px'>{title}</div>
          <textarea id='ta{key}' style='width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;'>{text}</textarea>
          <button onclick=\"navigator.clipboard.writeText(document.getElementById('ta{key}').value)\" style='margin-top:8px;padding:6px 10px;border-radius:8px;border:1px solid #d1d5db;cursor:pointer;'>📋 복사</button>
        </div>
        """, height=height+110)

    topic_all = st.text_input("주제(통합)", value="치매 예방 두뇌 건강법", key="ytbl_topic_all")
    audience_all = st.selectbox("타깃(통합)", ["50~70대 시니어", "30~50대 주부", "일반 성인"], index=0, key="ytbl_aud_all")

    st.markdown("**출력 순서 고정** — 유튜브: 제목→설명→자막(챕터별 복사)→이미지 프롬프트(복사)→해시태그 / 블로그: 제목→본문(≥1500자)→이미지 프롬프트→태그")

    colY, colB = st.columns(2)

    with colY:
        st.subheader("📺 유튜브 패키지")
        if st.button("▶ 유튜브 생성", key="yt_all_btn"):
            sys = (
                "You are a Korean YouTube content writer. Output only valid JSON following the schema. "
                "Create longer, natural Korean text for seniors."
            )
            user = f"""
[주제] {topic_all}
[타깃] {audience_all}
[요구]
- JSON schema:
{{
  "titles": ["...", "...", "..."],
  "description": "...",
  "chapters": [
     {{"title":"인트로","script":"..."}},
     {{"title":"챕터1","script":"..."}},
     {{"title":"챕터2","script":"..."}},
     {{"title":"챕터3","script":"..."}},
     {{"title":"챕터4","script":"..."}},
     {{"title":"챕터5","script":"..."}},
     {{"title":"엔딩","script":"..."}}
  ],
  "image_prompts": [
     {{"label":"썸네일","en":"...","ko":"..."}},
     {{"label":"본문1","en":"...","ko":"..."}},
     {{"label":"본문2","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#..", "#.."]
}}
- Rules:
  1) Put video titles first in array. 2) Description concise but inviting. 3) Each chapter script 2~4 sentences for Vrew.
  4) Image prompts must be Korean senior context; provide English prompt and Korean gloss. 5) Hashtags at the end.
"""
            with st.spinner("유튜브 생성 중…"):
                raw = chat_complete(sys, user, model_text, temperature)
            try:
                data = json.loads(raw)
            except Exception:
                sys2 = sys + " Return ONLY compact JSON without prose."
                raw = chat_complete(sys2, user, model_text, temperature)
                data = json.loads(raw)

            st.success("유튜브 패키지 생성 완료")
            st.markdown("**① 영상 제목 3개**")
            st.write("
".join([f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]))
            copy_block("영상 제목 전체 복사", "
".join(data.get("titles", [])), 100)
            st.markdown("**② 영상 설명**")
            copy_block("영상 설명 복사", data.get("description", ""), 160)
            st.markdown("**③ 브루 자막 (챕터별 복사 + 전체 복사)**")
            chapters = data.get("chapters", [])
            all_script = []
            for i, ch in enumerate(chapters):
                title = ch.get("title", f"챕터 {i+1}")
                script = ch.get("script", "")
                all_script.append(script)
                copy_block(f"[{title}] 자막 복사", script, 140)
            copy_block("브루 자막 — 전체 일괄 복사", "

".join(all_script), 220)
            st.markdown("**④ 이미지 프롬프트 (영문 + 한글, 복사버튼)**")
            for p in data.get("image_prompts", []):
                en = p.get("en", ""); ko = p.get("ko", "")
                lbl = p.get("label", "이미지")
                copy_block(f"[{lbl}] EN Prompt", en, 100)
                copy_block(f"[{lbl}] KO 해석", ko, 80)
            st.markdown("**⑤ 해시태그 (마지막)**")
            tags = " ".join(data.get("hashtags", []))
            copy_block("해시태그 복사", tags, 80)

    with colB:
        st.subheader("✍️ 블로그 패키지 (네이버 ≥1500자)")
        if st.button("▶ 블로그 생성", key="blog_all_btn"):
            sys = (
                "You are a Korean Naver-SEO writer. Output only JSON. Ensure body length ≥ 1500 Korean characters."
            )
            user = f"""
[주제] {topic_all}
[규칙]
- JSON schema:
{{
  "titles": ["...", "...", "..."],
  "body": "(>=1500자 한국어 본문)",
  "image_prompts": [
     {{"label":"대표","en":"...","ko":"..."}},
     {{"label":"본문1","en":"...","ko":"..."}},
     {{"label":"본문2","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#.."]
}}
- Rules: titles first; image prompts English+Korean; hashtags appear last; tone friendly for seniors; short paragraphs.
"""
            with st.spinner("블로그 생성 중…"):
                raw = chat_complete(sys, user, model_text, temperature)
            try:
                data = json.loads(raw)
            except Exception:
                sys2 = sys + " Return ONLY compact JSON without prose."
                raw = chat_complete(sys2, user, model_text, temperature)
                data = json.loads(raw)

            st.success("블로그 패키지 생성 완료")
            st.markdown("**① 블로그 제목 3개**")
            st.write("
".join([f"{i+1}. {t}" for i, t in enumerate(data.get("titles", [])[:3])]))
            copy_block("블로그 제목 전체 복사", "
".join(data.get("titles", [])), 100)
            st.markdown("**② 본문 (≥1500자)**")
            copy_block("블로그 본문 복사", data.get("body", ""), 300)
            st.markdown("**③ 이미지 프롬프트 (영문 + 한글)**")
            for p in data.get("image_prompts", []):
                en = p.get("en", ""); ko = p.get("ko", "")
                lbl = p.get("label", "이미지")
                copy_block(f"[{lbl}] EN Prompt", en, 100)
                copy_block(f"[{lbl}] KO 해석", ko, 80)
            st.markdown("**④ 해시태그 (마지막)**")
            copy_block("블로그 해시태그 복사", "
".join(data.get("hashtags", [])), 100)
except Exception as _e:
    st.warning(f"통합 섹션 로딩 경고: {_e}")

