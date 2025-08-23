# -*- coding: utf-8 -*-
# 새출발용 안정화본 — 블로그·유튜브 통합 생성기
# 동기 실행 · JSON 강제 · 자동 재시도/모델 스위치 · 폴백 보장 · 세션 안전

import os, re, json, time, uuid, html
from datetime import datetime, timezone, timedelta
import streamlit as st
from streamlit.components.v1 import html as comp_html
from openai import OpenAI

# ============== 기본 ==============
KST = timezone(timedelta(hours=9))
APP_TITLE = "⚡ 블로그·유튜브 통합 생성기 (안정화본)"
CTA = "강쌤철물 집수리 관악점에 지금 바로 문의주세요. 상담문의: 010-2276-8163"

st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="wide")
st.title(APP_TITLE)
st.caption(f"KST {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} · 한국어 고정 · EN 이미지 프롬프트 · 동기 실행")

# 세션 기본값(항상 setdefault)
st.session_state.setdefault("model_text", "gpt-4o-mini")
st.session_state.setdefault("people_taste", False)

# components.html key 지원 확인(환경차 보호)
try:
    HTML_SUPPORTS_KEY = 'key' in comp_html.__code__.co_varnames
except Exception:
    HTML_SUPPORTS_KEY = False

# ============== OpenAI ==============
def _load_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))

def _client() -> OpenAI:
    ak = _load_api_key()
    if not ak:
        st.error("❌ OPENAI_API_KEY 미설정. Streamlit Secrets 또는 환경변수에 등록하세요.")
        st.stop()
    return OpenAI(api_key=ak, timeout=50)

# 부팅 헬스체크(명확)
try:
    _ = _client().models.list()
    st.success("✅ OpenAI API 연결 OK")
except Exception as e:
    st.error("⚠️ OpenAI API 연결 실패")
    st.exception(e)
    st.stop()

# ============== 유틸 ==============
def _copy_iframe_html(title: str, esc_text: str, height: int) -> str:
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8" />
<style>
body{{margin:0;font-family:system-ui,-apple-system,'Noto Sans KR',Arial}}
.wrap{{border:1px solid #e5e7eb;border-radius:10px;padding:10px}}
.ttl{{font-weight:600;margin-bottom:6px}}
textarea{{width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;white-space:pre-wrap;box-sizing:border-box;font-family:ui-monospace,Menlo,Consolas}}
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

def copy_block(title: str, text: str, height: int = 160):
    esc_t = (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    html_str = _copy_iframe_html(title or "", esc_t, height)
    try:
        if HTML_SUPPORTS_KEY: comp_html(html_str, height=height+110, scrolling=False, key=f"copy_{uuid.uuid4().hex}")
        else:                  comp_html(html_str, height=height+110, scrolling=False)
    except Exception:
        st.text_area(title or "", text or "", height=height)

def find_json(s: str) -> str:
    if not isinstance(s, str): return ""
    m = re.search(r"\{.*\}", s, re.S)
    return m.group(0) if m else ""

def parse_json(s: str, fallback: dict) -> dict:
    try:
        return json.loads(find_json(s) or "") or fallback
    except Exception:
        return fallback

# ============== LLM 호출( JSON 강제 + 재시도 + 모델 스위치 ) ==============
def call_json(system: str, user: str, model: str, temperature: float) -> str:
    cli = _client()

    def _once(md: str) -> str:
        r = cli.chat.completions.create(
            model=md,
            temperature=temperature,
            max_tokens=1800,                 # 과도 토큰 방지
            timeout=50,
            response_format={"type": "json_object"},  # JSON 강제
            messages=[{"role":"system","content":system},
                      {"role":"user","content":user}],
        )
        return r.choices[0].message.content.strip()

    waits=[0.7,1.2,2.0]
    # 1차: 선택 모델
    for i,w in enumerate(waits):
        try: return _once(model)
        except Exception:
            if i < len(waits)-1: time.sleep(w)
    # 2차: gpt-4o 스위치
    for i,w in enumerate(waits):
        try: return _once("gpt-4o")
        except Exception:
            if i < len(waits)-1: time.sleep(w)
    return ""  # 최종 실패시 빈 문자열

# ============== 타깃/이미지 ==============
def detect_demo(topic: str):
    t=(topic or "").lower()
    age="성인"
    for pat,label in [(r"(유아|영유아|신생아)","유아"),(r"(아동|초등|키즈)","아동"),
                      (r"(청소년|10대)","청소년"),(r"20대","20대"),(r"30대","30대"),
                      (r"40대","40대"),(r"50대|장년|중년","50대"),(r"60대|시니어","60대"),
                      (r"70대|고령","70대")]:
        if re.search(pat,t): age=label; break
    if re.search(r"(남성|남자|아빠|형|삼촌|남편)", t): gender="남성"
    elif re.search(r"(여성|여자|엄마|언니|이모|아내)", t): gender="여성"
    else: gender="혼합"
    return age, gender

def img_en(base_en, age, gender, place, mood, shot, style):
    age_map={"유아":"toddlers","아동":"children","청소년":"teenagers","20대":"people in their 20s",
             "30대":"people in their 30s","40대":"people in their 40s","50대":"people in their 50s",
             "60대":"people in their 60s","70대":"people in their 70s","성인":"adults"}
    gender_map={"남성":"Korean man","여성":"Korean woman","혼합":"Korean men and women"}
    place_map={"한국 가정 거실":"modern Korean home living room interior",
               "한국 아파트 단지":"Korean apartment complex outdoor area",
               "한국 동네 공원":"local Korean neighborhood park",
               "한국 병원/검진센터":"Korean medical clinic interior",
               "한국형 주방/식탁":"modern Korean kitchen and dining table"}
    shot_map={"클로즈업":"close-up","상반신":"medium shot","전신":"full body shot","탑뷰/테이블샷":"top view table shot"}
    mood_map={"따뜻한":"warm","밝은":"bright","차분한":"calm","활기찬":"energetic"}
    style_map={"사진 실사":"realistic photography, high resolution","시네마틱":"cinematic photo style",
               "잡지 화보":"editorial magazine style","자연광":"natural lighting"}
    return (f"{gender_map.get(gender,'Korean men and women')} {age_map.get(age,'adults')} at a "
            f"{place_map.get(place,'modern Korean interior')}, {shot_map.get(shot,'medium shot')}, "
            f"{mood_map.get(mood,'warm')} mood, {style_map.get(style,'realistic photography, high resolution')}. "
            f"Context: {base_en}. natural lighting, high contrast, no text overlay, no captions, no watermarks, no logos.")

# ============== 사이드바 ==============
with st.sidebar:
    st.header("⚙️ 생성 설정")
    st.selectbox("모델", ["gpt-4o-mini","gpt-4o"], index=0, key="model_text")
    temperature = st.slider("창의성", 0.0, 1.2, 0.6, 0.1)

    st.markdown("---")
    target_chapter = st.selectbox("유튜브 자막 개수", [5,6,7], 0)
    include_thumb  = st.checkbox("썸네일 프롬프트 포함", value=True)

    st.markdown("---")
    st.markdown("### 🖼 이미지 옵션(한국 맥락)")
    img_age    = st.selectbox("연령", ["자동","유아","아동","청소년","20대","30대","40대","50대","60대","70대","성인"], 0)
    img_gender = st.selectbox("성별", ["자동","혼합","남성","여성"], 0)
    img_place  = st.selectbox("장소", ["한국 가정 거실","한국 아파트 단지","한국 동네 공원","한국 병원/검진센터","한국형 주방/식탁"], 0)
    img_mood   = st.selectbox("무드", ["따뜻한","밝은","차분한","활기찬"], 0)
    img_shot   = st.selectbox("샷", ["클로즈업","상반신","전신","탑뷰/테이블샷"], 1)
    img_style  = st.selectbox("스타일", ["사진 실사","시네마틱","잡지 화보","자연광"], 0)

    st.markdown("---")
    st.markdown("### 📝 블로그 옵션")
    blog_min   = st.slider("최소 길이(자)", 1500, 4000, 1800, 100)
    blog_imgs  = st.selectbox("이미지 프롬프트 수", [3,4,5,6], 2)
    tag_join   = st.radio("태그 결합 방식", ["띄어쓰기 한 줄","줄바꿈 여러 줄"], 0)

    st.markdown("---")
    if st.checkbox("강제 재생성(캐시 무시)", value=False):
        st.cache_data.clear()

# ============== 입력 ==============
st.subheader("🎯 주제 및 내용")
c1,c2,c3,c4 = st.columns([2,1,1,1])
with c1: topic = st.text_input("주제", value="50대 이후 조심해야 할 음식 TOP5")
with c2: tone  = st.selectbox("톤/스타일", ["시니어 친화형","전문가형","친근한 설명형"], 1)
with c3: mode_sel = st.selectbox("콘텐츠 유형", ["자동 분류","정보형(블로그 지수)","시공후기형(영업)"], 1)
with c4: target = st.selectbox("생성 대상", ["유튜브 + 블로그","유튜브만","블로그만"], 0)

def _classify(txt): 
    return "sales" if any(k in txt for k in ["시공","교체","설치","수리","누수","보수","후기","현장","관악","강쌤철물"]) else "info"
def _mode():
    if mode_sel=="정보형(블로그 지수)": return "info"
    if mode_sel=="시공후기형(영업)":   return "sales"
    return _classify(topic)
mode = _mode()

auto_age, auto_gender = detect_demo(topic)
final_age    = auto_age    if img_age=="자동" else img_age
final_gender = auto_gender if img_gender=="자동" else img_gender

st.caption("옵션 확인 후 아래 버튼으로 실행하세요.")
go = st.button("▶ 한 번에 생성", type="primary")
MODEL = st.session_state.get("model_text","gpt-4o-mini")

# ============== 스키마/폴백 ==============
def schema_for_llm(min_chars:int) -> str:
    return f'''{{
  "demographics": {{"age_group":"{final_age}","gender":"{final_gender}"}},
  "youtube": {{
    "titles": ["..."],
    "description": "...",
    "chapters": [{{"title":"...","script":"..."}}],
    "images": {{"thumbnail": {{"en":"(EN no text)"}}, "chapters": [{{"index":1,"en":"(EN no text)"}}]}},
    "hashtags": ["#.."]
  }},
  "blog": {{
    "titles": ["..."],
    "body": ">= {min_chars}자, 구조: 서론→핵심5→체크리스트(6~8)→자가진단(5)→FAQ(3)→마무리. 본문 내 [이미지:대표/본문1/본문2] 포함",
    "images": [{{"label":"대표","en":"(EN no text)"}}],
    "tags": ["#.."]
  }}
}}'''

def fb_youtube(topic:str, n:int):
    ch=[{"title":f"{topic} 핵심 포인트 {i+1}",
         "script":f"{topic} 관련 핵심 포인트 {i+1}을(를) 현장 기준으로 간단히 설명합니다."} for i in range(n)]
    return {"titles":[f"{topic} 가이드 {i+1}" for i in range(10)],
            "description":f"{topic} 요약 가이드입니다.",
            "chapters":ch,
            "images":{"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                      "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]},
            "hashtags":["#집수리","#현장팁","#강쌤철물"]*5}

def fb_blog(topic:str, img_n:int, mode:str):
    body=(f"## {topic}\n\n네트워크 지연 시 제공되는 안전본입니다.\n\n"
          "### 핵심 5가지\n1) 현장 진단\n2) 원인 추정\n3) 준비물 체크\n4) 순서대로 작업\n5) 마무리 점검\n\n"
          "### 체크리스트(6~8)\n- 누수/결선/고정\n- 소음/진동\n- 경고등/오류코드\n- 마감\n- 재방문 필요성\n- 사진 기록\n\n"
          "### 자가진단(5)\n- 증상 지속 여부\n- 특정 조건만 발생?\n- 최근 교체/수리 이력\n- 임시조치 효과\n- A/S 대상 여부\n\n"
          "### FAQ(3)\n- 시간: 1~3시간\n- 비용: 난이도/부품 의존\n- 준비: 공간확보·전원/밸브 차단\n\n"
          "[이미지:대표]\n[이미지:본문1]\n[이미지:본문2]\n")
    if mode=="sales": body += f"\n{CTA}"
    imgs=[{"label":"대표","en":"Korean home context, no text overlay"}]+[
        {"label":f"본문{i}","en":f"support visual for section {i} of '{topic}' (no text overlay)"} for i in range(1,img_n)
    ]
    return {"titles":[f"{topic} 블로그 {i+1}" for i in range(10)],
            "body":body,"images":imgs[:img_n],
            "tags":["#집수리","#시공후기","#관악구","#강쌤철물"]}

# ============== 생성 ==============
def gen_youtube(topic,tone,n,mode,model):
    sys=(
      "[voice] 20년 차 현장 전문가 '강쌤'. 차분·존대, 가벼운 유머. 2~3문장마다 호흡.\n"
      "사례/비교/주의/대안 포함. 마무리 2줄 요약+체크 3~5.\n"
      "한국 맥락. 반드시 JSON만 반환."
    )
    user=(f"[topic]{topic}\n[tone]{tone}\n[mode]{'info' if mode=='info' else 'sales'}\n[N]{n}\n"
          f"[demo] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(0)}")
    raw=call_json(sys,user,model,min(temperature,0.6))
    data=parse_json(raw,{})
    if not data.get("youtube"):  # 모델 스위치 재시도
        data=parse_json(call_json(sys,user,"gpt-4o",0.6),{})
    yt=data.get("youtube") or {}
    if not yt.get("titles"): yt["titles"]=[f"{topic} 가이드 {i+1}" for i in range(10)]
    if (not yt.get("description")) or (not yt.get("chapters")): yt=fb_youtube(topic,n)
    # CTA
    if mode=="sales":
        desc=(yt.get("description","") or "").rstrip()
        if CTA not in desc: yt["description"]=(desc+f"\n{CTA}").strip()
    # 이미지 기본
    if "images" not in yt:
        yt["images"]={"thumbnail":{"en":"Korean home thumbnail, no text overlay"},
                      "chapters":[{"index":i+1,"en":"support visual, no text overlay"} for i in range(n)]}
    return yt

def gen_blog(topic,tone,mode,min_chars,img_n,model):
    sys=(
      "[voice] 20년 차 현장 전문가 '강쌤'. 차분·존대. 현장 디테일 1~2개.\n"
      f"길이>={min_chars}자. 구조: 서론→핵심5→체크리스트(6~8)→자가진단(5)→FAQ(3)→마무리. JSON만."
    )
    user=(f"[topic]{topic}\n[tone]{tone}\n[mode]{'info' if mode=='info' else 'sales'}\n"
          f"[demo] age={final_age}, gender={final_gender}\n[schema]\n{schema_for_llm(min_chars)}")
    raw=call_json(sys,user,model,min(temperature,0.6))
    data=parse_json(raw,{})
    if not data.get("blog"):  # 모델 스위치 재시도
        data=parse_json(call_json(sys,user,"gpt-4o",0.6),{})
    blog=data.get("blog") or {}
    if (not blog.get("body")) or (len(blog.get("body",""))<500): blog=fb_blog(topic,img_n,mode)
    if mode=="sales" and CTA not in blog.get("body",""):
        blog["body"]=(blog.get("body","").rstrip()+f"\n\n{CTA}")
    # 이미지 개수 맞추기
    imgs=(blog.get("images") or [])[:img_n]
    while len(imgs)<img_n:
        i=len(imgs)
        imgs.append({"label":"대표" if i==0 else f"본문{i}",
                     "en":f"support visual for section {i} of '{topic}' (no text overlay)"})
    blog["images"]=imgs
    if not blog.get("titles"): blog["titles"]=[f"{topic} 블로그 {i+1}" for i in range(10)]
    if not blog.get("tags"): blog["tags"]=["#집수리","#시공후기","#관악구","#강쌤철물"]
    return blog

# ============== 내보내기 ==============
def join_tags(tags:list, style:str) -> str:
    return "\n".join(tags) if style=="줄바꿈 여러 줄" else " ".join(tags)

def build_youtube_txt(yt:dict) -> str:
    titles="\n".join(f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:10]))
    chapters="\n\n".join(f"[챕터 {i+1}] {c.get('title','')}\n{c.get('script','')}" for i,c in enumerate(yt.get("chapters",[])))
    desc=yt.get("description","").strip()
    tags=" ".join(yt.get("hashtags",[]))
    return f"# YouTube Package\n\n## Titles\n{titles}\n\n## Description\n{desc}\n\n## Chapters\n{chapters}\n\n## Hashtags\n{tags}\n"

def build_blog_md(blog:dict) -> str:
    titles="\n".join(f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:10]))
    body=blog.get("body","")
    tags=" ".join(blog.get("tags",[]))
    return f"# Blog Package\n\n## Titles\n{titles}\n\n## Body\n{body}\n\n## Tags\n{tags}\n"

# ============== 실행 ==============
if go:
    try:
        do_yt = target in ["유튜브 + 블로그","유튜브만"]
        do_bl = target in ["유튜브 + 블로그","블로그만"]

        st.info("🔧 실행 중… (동기 처리)")
        results={}

        if do_yt:
            st.write("📺 유튜브 생성 중…")
            results["yt"]=gen_youtube(topic,tone,target_chapter,mode,MODEL)

        if do_bl:
            st.write("📝 블로그 생성 중…")
            results["blog"]=gen_blog(topic,tone,mode,blog_min,blog_imgs,MODEL)

        st.success("✅ 생성 완료")

        # 유튜브
        if do_yt:
            yt=results.get("yt",{})
            st.markdown("## 📺 유튜브 패키지")
            copy_block("① 영상 제목(SEO 10)", "\n".join([f"{i+1}. {t}" for i,t in enumerate(yt.get("titles",[])[:10])]), 160)
            copy_block("② 영상 설명", yt.get("description",""), 160)
            chs=yt.get("chapters",[])[:target_chapter]
            vrew="\n".join([(c.get("script","") or "").replace("\n"," ") for c in chs])
            copy_block("③ 브루 자막 — 전체 일괄(Vrew)", vrew, 220)
            if include_thumb:
                copy_block("[썸네일] EN",
                           img_en(f"YouTube thumbnail for topic: {topic}. Korean home context.",
                                  final_age, final_gender, img_place, img_mood, img_shot, img_style), 110)
            copy_block("⑤ 해시태그(20)", " ".join(yt.get("hashtags",[])), 90)
            st.download_button("⬇️ 유튜브 패키지 .txt",
                               build_youtube_txt(yt).encode("utf-8"),
                               file_name="youtube_package.txt", mime="text/plain")

        # 블로그
        if do_bl:
            blog=results.get("blog",{})
            st.markdown("---"); st.markdown("## 📝 블로그 패키지")
            copy_block("① 블로그 제목(SEO 10)", "\n".join([f"{i+1}. {t}" for i,t in enumerate(blog.get("titles",[])[:10])]), 160)
            copy_block("② 본문 (이미지 앵커 포함)", blog.get("body",""), 420)
            copy_block("②-β 본문+해시태그 (한 번에 복사)",
                       f"{blog.get('body','').rstrip()}\n\n{join_tags(blog.get('tags',[]), tag_join)}", 460)
            if blog.get("images"):
                exp = st.expander("③ 이미지 프롬프트 (EN only, no text overlay)", expanded=False)
                with exp:
                    for p in blog.get("images",[]):
                        base = p.get("en","") or f"support visual for section '{p.get('label','')}'"
                        copy_block(f"[{p.get('label','이미지')}] EN",
                                   img_en(base, final_age, final_gender, img_place, img_mood, img_shot, img_style), 110)
            copy_block("④ 태그(20)", join_tags(blog.get("tags",[]), tag_join), 100)
            st.download_button("⬇️ 블로그 패키지 .md",
                               build_blog_md(blog).encode("utf-8"),
                               file_name="blog_package.md", mime="text/markdown")

    except Exception as e:
        st.error("⚠️ 실행 중 오류가 발생했습니다. 아래 로그 확인:")
        st.exception(e)

st.markdown("---")
st.caption("동기 실행 · JSON 강제 · 재시도/모델 스위치 · 폴백 보장 · 세션 안전 접근 · 캐시/스레드/워치독 제거")
