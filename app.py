import streamlit as st
from datetime import datetime
import pyperclip

# ----------------------------
# 초기 설정
# ----------------------------
st.set_page_config(page_title="블로그 & 유튜브 자동화 도우미", layout="wide")
st.title("📌 블로그 & 유튜브 자동화 생성기")
st.write("원하는 주제를 입력하고, 유튜브 영상과 블로그 글을 한 번에 생성하세요!")

# ----------------------------
# 사용자 입력
# ----------------------------
topic = st.text_input("주제 입력", placeholder="예: 치매 예방 두뇌 건강법")
generate_button = st.button("콘텐츠 생성하기")

# ----------------------------
# 복사 버튼 함수
# ----------------------------
def copy_to_clipboard(text):
    pyperclip.copy(text)
    st.success("복사 완료 ✅")

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
        f"Healthy Korean senior couple cooking brain-boosting food, natural lighting, realistic, 4K",
        f"Active Korean seniors walking in the park, happy, bright colors, cinematic, 4K",
        f"Calm Korean elderly man meditating indoors, soft lighting, photo-realistic, 4K"
    ]

    return titles, script, image_prompts

def generate_blog_content(topic):
    # ✅ 블로그 제목 (최적화된 3개)
    titles = [
        f"{topic} 전문가가 알려주는 비밀 꿀팁",
        f"50대 이후 꼭 알아야 할 {topic} 완벽 가이드",
        f"두뇌 건강을 위한 {topic} 핵심 전략"
    ]

    # ✅ 블로그 본문 (1,500자 이상)
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
# ---
