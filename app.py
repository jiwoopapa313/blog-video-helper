import os
from datetime import datetime, timezone, timedelta

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="블로그·영상 통합 도우미", page_icon="🧰", layout="wide")
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

st.title("🧰 블로그·영상 통합 도우미")
st.caption(f"KST 현재 시각: {now_kst} · 블로그/숏츠/이미지 한 번에 생성")

with st.sidebar:
    st.header("⚙️ 공통 설정")
    st.info("※ Streamlit Cloud > Secrets 에 OPENAI_API_KEY만 넣으면 여기 입력 불필요", icon="🔐")
    model_text = st.selectbox("텍스트 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    model_image = st.selectbox("이미지 모델", ["gpt-image-1"], index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.6, 0.1)

def _get_client():
    api_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("OPENAI_API_KEY가 없습니다. Streamlit Cloud의 Secrets에 등록하세요.", icon="⚠️")
    return OpenAI(api_key=api_key)

def chat_complete(system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}]
    )
    return resp.choices[0].message.content.strip()

def generate_image(prompt: str, size: str, model: str) -> bytes:
    client = _get_client()
    img = client.images.generate(model=model, prompt=prompt, size=size)
    import base64
    return base64.b64decode(img.data[0].b64_json)

tab1, tab2, tab3, tab4 = st.tabs(["📊 사업계획서","🛒 상품 URL → 콘텐츠","📝 블로그 SEO","🖼️ 썸네일/이미지"])

with tab1:
    st.subheader("📊 사업 아이디어 → 한국형 사업계획서")
    c1, c2 = st.columns(2)
    with c1:
        biz_title = st.text_input("사업 아이디어/업종", placeholder="예: 관악구 집수리 + 블로그·영상 자동화")
        target = st.text_input("타깃 고객", placeholder="예: 관악·서초·동작 소상공인, 1인 셀러")
        problem = st.text_area("고객 문제/니즈", placeholder="예: 콘텐츠 제작 어려움, 상세페이지 작성 시간 부족", height=100)
    with c2:
        usp = st.text_area("차별점(USP)", placeholder="예: 네이버 상위노출 템플릿 + 쿠팡/스마트스토어 자동화", height=100)
        revenue = st.text_input("수익모델", placeholder="예: 월 구독형(29,000~99,000) + 템플릿 판매 + 커스텀")
        channels = st.text_input("마케팅 채널", placeholder="예: 네이버 블로그/지도/카페, 유튜브 숏츠")
    if st.button("사업계획서 생성", type="primary"):
        if not biz_title:
            st.error("사업 아이디어/업종을 입력해주세요.")
        else:
            sys = ("당신은 한국 소상공인 대상 사업계획서 전문가. KST, 보수적·팩트 위주·과장 금지, 쉬운 문장. "
                   "구성: 1)개요 2)시장/경쟁 3)고객/문제 4)해결책/제품 5)수익모델 6)90일 실행계획 7)리스크/대응 8)FAQ 9)10줄 요약.")
            user = f"[아이디어]{biz_title}\n[타깃]{target}\n[문제]{problem}\n[USP]{usp}\n[수익]{revenue}\n[채널]{channels}"
            with st.spinner("생성 중..."):
                txt = chat_complete(sys, user, model_text, temperature)
            st.success("완료")
            st.download_button("📄 저장 (business_plan.txt)", txt, file_name="business_plan.txt")
            st.text_area("미리보기", txt, height=380)

with tab2:
    st.subheader("🛒 상품 URL → 상세페이지/숏츠/블로그")
    url = st.text_input("상품 URL(쿠팡/스마트스토어 등)")
    tone = st.selectbox("톤/스타일", ["작업자 시선·쉬운 말투(기본)","전문가형","세일즈형(자극)"], index=0)
    include_coupang = st.checkbox("쿠팡파트너스 고지 문구 포함", value=False)
    local_tags = "#관악구철물점 #관악구집수리 #서초구집수리 #동작구집수리 #전기설비 #수도설비 #전등교체 #수전교체 #수도꼭지"
    if st.button("콘텐츠 생성", type="primary"):
        style_note = "작업자 시선 + 쉬운 말투" if tone.startswith("작업자") else tone
        disclaimer = "※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다." if include_coupang else ""
        sys = ("당신은 한국 이커머스 상세/블로그/숏츠 제작자. 사실 위주, 쉬운 말투, 허위·과장 금지. "
               "출력: 1)상세 개요 2)스펙·장점 표 3)구매 전 체크리스트 "
               "4)40초 숏츠 대본(6~7줄, 마지막: '지금 프로필을 클릭하시고, 제품을 확인하세요!') "
               "5)네이버 블로그 본문(이미지 위치 [이미지: ...]) 6)해시태그 두 형식(한 줄/줄바꿈) 7)주의사항.")
        user = f"[상품URL]{url}\n[스타일]{style_note}\n[지역 해시태그]{local_tags}\n[쿠팡 문구]{disclaimer}"
        with st.spinner("생성 중..."):
            txt = chat_complete(sys, user, model_text, temperature)
        st.success("완료")
        st.download_button("📝 저장 (product_content.txt)", txt, file_name="product_content.txt")
        st.text_area("미리보기", txt, height=380)

with tab3:
    st.subheader("📝 네이버 블로그 최적화 글")
    topic = st.text_input("주제/키워드", placeholder="예: 양재동 건강식품 매장 LED 안정기 수리 현장")
    must_tags = st.text_area("항상 포함할 해시태그(본문꾸미기용)",
                             value="#관악구철물점 #관악구집수리 #서초구집수리 #동작구집수리 #전기설비 #수도설비 #전등교체 #수전교체 #수도꼭지",
                             height=70)
    length = st.selectbox("길이", ["1000~1500자","1500~2000자","2000자 이상"], index=1)
    if st.button("블로그 글 생성", type="primary"):
        sys = ("당신은 네이버 상위노출 글 작성자. 쉬운 말투, 리스트 중심, 지역키워드 자연 반복, 120자 메타설명, CTA 포함, "
               "이미지 위치 표기, 끝에 해시태그 두 형식(한 줄/줄바꿈) 동시 출력.")
        user = f"[주제]{topic}\n[길이]{length}\n[태그]{must_tags}\n[지역]관악구·서초구·동작구"
        with st.spinner("생성 중..."):
            txt = chat_complete(sys, user, model_text, temperature)
        st.success("완료")
        st.download_button("📝 저장 (naver_blog.txt)", txt, file_name="naver_blog.txt")
        st.text_area("미리보기", txt, height=380)

with tab4:
    st.subheader("🖼️ 썸네일/이미지 자동 생성 (한국인 기준)")
    prompt = st.text_area("이미지 프롬프트(영문 권장)",
                          value=("A clean, modern Korean home interior, Korean hands installing LED edge light; "
                                 "bold Korean title text '혈압 잡는 스트레칭 3가지' at top; high contrast; thumbnail framing; "
                                 "avoid extra small text; suitable for YouTube thumbnail; 16:9; "
                                 "Korean Hangul high legibility, large bold text"),
                          height=110)
    size = st.selectbox("사이즈", ["1024x1024","1024x1792","1792x1024"], index=0)
    if st.button("이미지 생성", type="primary"):
        try:
            with st.spinner("이미지 생성 중..."):
                png_bytes = generate_image(prompt, size=size, model=model_image)
            st.success("완료")
            st.image(png_bytes, caption="생성 미리보기")
            st.download_button("🖼️ 다운로드 (thumbnail.png)", png_bytes, file_name="thumbnail.png")
            st.info("한글이 깨지면 프롬프트 끝에 'Korean Hangul big bold text' 추가.")
        except Exception as e:
            st.error(f"이미지 생성 실패: {e}")
            st.caption("OPENAI_API_KEY / 모델명 / 사용량 한도 확인.")
