import streamlit as st
from datetime import datetime
from streamlit.components.v1 import html as comp_html

# ----------------------------
# 초기 설정
# ----------------------------
st.set_page_config(page_title="블로그 & 유튜브 자동화 도우미", layout="wide")
st.title("📌 블로그 & 유튜브 자동화 생성기")
st.write("원하는 주제를 입력하고, 유튜브 영상과 블로그 글을 한 번에 생성하세요!")

# ----------------------------
# 복사 컴포넌트
# ----------------------------
def copy_block(title: str, text: str, height: int = 160):
    """텍스트 + 📋복사 버튼 UI (의존성 없음)"""
    escaped = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    comp_html(f"""
    <div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin:8px 0;">
      <div style="font-weight:600;margin-bottom:6px">{title}</div>
      <textarea id="ta" style="width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;">{escaped}</textarea>
      <button onclick="navigator.clipboard.writeText(document.getElementById('ta').value)"
              style="margin-top:8px;padding:6px 10px;border-radius:8px;border:1px solid #d1d5db;cursor:pointer;">
        📋 복사
      </button>
    </div>
    """, height=height+110)

# ----------------------------
# 사용자 입력
# ----------------------------
topic = st.text_input("주제 입력", placeholder="예: 치매 예방 두뇌 건강법")
generate_button = st.button("콘텐츠 생성하기")

# ----------------------------
# 콘텐츠 생성 함수 (샘플)
# ----------------------------
def generate_youtube_content(topic):
    # ✅ 유튜브 제목 (최적화된 3개)
    titles = [
        f"{topic} 완벽 가이드! 50대 이후 꼭 봐야 할 필수 정보",
        f"두뇌 건강을 위한 {topic} 실전 방법 5가지",
        f"{topic} 전문가가 알려주는 비밀 꿀팁"
    ]
    # ✅ 브루 자막용 대본 (챕터별)
    script = [
        "오프닝: 두뇌 건강을 지키는 첫 번째 비밀, 시작합니다!",
        "1장: 균형 잡힌 식단의 중요성",
        "2장: 매일 30분 운동 습관 만들기",
        "3장: 숙면과 스트레스 관리",
        "4장: 두뇌를 깨우는 취미 생활",
        "엔딩: 오늘부터 작은 변화로 두뇌 건강을 지켜보세요!"
    ]
    # ✅ 이미지 생성 프롬프트
    image_prompts = [
        "Healthy Korean senior couple cooking brain-boosting food, natural lighting, realistic, 4K",
        "Active Korean seniors walking in the park, happy, bright colors, cinematic, 4K",
        "Calm Korean elderly man meditating indoors, soft lighting, photo-realistic, 4K"
    ]
    return titles, script, image_prompts

def generate_blog_content(topic):
    # ✅ 블로그 제목 (최적화된 3개)
    titles = [
        f"{topic} 전문가가 알려주는 비밀 꿀팁",
        f"50대 이후 꼭 알아야 할 {topic} 완벽 가이드",
        f"두뇌 건강을 위한 {topic} 핵심 전략"
    ]
    # ✅ 블로그 본문 (1,500자 이상 목표)
    body = f"""
# {topic} 완벽 가이드

## 1. 왜 두뇌 건강이 중요한가요?
두뇌는 신체의 모든 기능을 조절하는 핵심 기관으로, 노화가 진행되면서 인지 기능 저하와 질병 위험이 높아집니다.
특히 50대 이후에는 두뇌 건강을 지키는 습관이 필수입니다.

## 2. 두뇌 건강을 지키는 핵심 습관
- **균형 잡힌 식단**: 오메가3, 항산화 성분, 비타민을 충분히 섭취하세요.
- **규칙적인 운동**: 하루 30분 이상 걷기만 해도 충분히 도움이 됩니다.
- **숙면 습관**: 깊고 규칙적인 수면은 기억력 향상에 큰 도움이 됩니다.
- **두뇌 자극 활동**: 책 읽기, 악기 연주, 새로운 취미 배우기가 효과적입니다.
- **사회적 교류**: 가족 및 친구와의 대화는 우울증과 치매 예방에 좋습니다.

## 3. 전문가 TIP
“두뇌 건강을 위한 가장 큰 비결은 작은 습관의 반복입니다.”

---

**결론**
오늘부터 실천 가능한 작은 습관을 시작해 보세요.
두뇌 건강은 관리하는 만큼 나이를 거스릅니다.
"""
    return titles, body

# ----------------------------
# 버튼 클릭 시 실행
# ----------------------------
if generate_button:
    if topic.strip() == "":
        st.error("주제를 입력해주세요.")
    else:
        # ===== 유튜브 =====
        st.subheader("🎬 유튜브 콘텐츠")
        yt_titles, yt_script, yt_images = generate_youtube_content(topic)

        st.markdown("### 📌 추천 영상 제목")
        yt_titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(yt_titles)])
        copy_block("영상 제목 (복사 가능)", yt_titles_text, 120)

        st.markdown("### 🎤 브루 자막 대본")
        script_text = "\n".join(yt_script)
        copy_block("브루 자막 (복사 가능)", script_text, 220)

        st.markdown("### 🖼 이미지 프롬프트")
        image_text = "\n".join(yt_images)
        copy_block("이미지 프롬프트 (복사 가능)", image_text, 160)

        st.divider()

        # ===== 블로그 =====
        st.subheader("📝 블로그 콘텐츠")
        blog_titles, blog_body = generate_blog_content(topic)

        st.markdown("### 📌 최적화 블로그 제목")
        blog_titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(blog_titles)])
        copy_block("블로그 제목 (복사 가능)", blog_titles_text, 120)

        st.markdown("### 📄 블로그 본문")
        copy_block("블로그 본문 (복사 가능)", blog_body, 420)
