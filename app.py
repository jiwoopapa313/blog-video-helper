import streamlit as st
from streamlit.components.v1 import html as comp_html
import uuid
import html
import inspect

# ========== 환경 호환성 체크 ==========
try:
    HTML_SUPPORTS_KEY = 'key' in inspect.signature(comp_html).parameters
except Exception:
    HTML_SUPPORTS_KEY = False

# ========== 페이지 설정 ==========
st.set_page_config(page_title="블로그 자동 생성기", layout="wide")
st.title("📝 네이버 블로그 자동 생성 통합툴")

# ========== 복사 버튼 함수 ==========
def copy_block(title: str, text: str, height: int = 200):
    esc_t = (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    html_str = f"""
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
"""
    if HTML_SUPPORTS_KEY:
        comp_html(html_str, height=height+110, scrolling=False, key=f"copy_{uuid.uuid4().hex}")
    else:
        with st.container():
            comp_html(html_str, height=height+110, scrolling=False)

# ========== 입력 폼 ==========
st.subheader("📌 블로그 생성 정보 입력")
col1, col2 = st.columns(2)
with col1:
    location = st.text_input("시공 지역", "서울 관악구")
    work_type = st.text_input("작업 내용", "전등 교체")
with col2:
    keyword = st.text_input("핵심 키워드", "관악구 집수리")
    images = st.slider("이미지 첨부 개수", 1, 5, 3)

# ========== 생성 버튼 ==========
if st.button("🚀 블로그 글 생성하기"):
    st.success("✅ 블로그 글이 성공적으로 생성되었습니다!")

    # 예시 블로그 내용
    blog_content = f"""
[{location} {work_type} 시공 후기]
안녕하세요! 강쌤철물입니다.
오늘은 {location}에서 진행한 {work_type} 현장을 소개해드릴게요.

📌 작업 개요
- 지역: {location}
- 작업 내용: {work_type}
- 소요 시간: 약 1시간

💡 작업 포인트
1. 안전을 위해 전원 차단 필수
2. 고효율 자재 사용으로 전기세 절감
3. 시공 후 깔끔한 마감 처리

시공 전/후 비교 이미지를 보시면 훨씬 이해가 쉬워요!
"""
    # 블로그 본문 복사 블록
    copy_block("블로그 본문", blog_content, height=300)

    # 해시태그 생성
    hashtags = "#관악구철물점 #관악구집수리 #서초구집수리 #동작구집수리 #전기설비 #수도설비 #전등교체 #수전교체 #수도꼭지"
    copy_block("해시태그", hashtags, height=100)

    # 이미지 안내
    st.info(f"이미지 {images}장 자동 첨부됨 (시공 전 / 진행중 / 시공 후)")
