# =============================
# UI 유틸: 복사 가능한 블록 (키 없이 안정 동작)  ✅FINAL
# =============================
def copy_block(title: str, text: str, height: int = 160):
    """
    - components.html의 key 미지원 환경에서도 에러 없이 동작
    - 한 컴포넌트 안에 textarea + 버튼 + JS를 모두 넣어 DOM 분리 이슈 제거
    - 버튼은 textarea를 참조하지 않고, 스크립트 내부 문자열을 복사하므로 충돌 없음
    """
    # 안전한 이스케이프를 위해 JSON 문자열로 주입
    import json as _json
    content_js = _json.dumps(text or "", ensure_ascii=False)

    html_str = f"""
    <div style='border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin:8px 0;'>
      <div style='font-weight:600;margin-bottom:6px'>{title}</div>

      <textarea
        readonly
        style='width:100%;height:{height}px;border:1px solid #d1d5db;border-radius:8px;padding:8px;'
      >{{content}}</textarea>

      <button
        style='margin-top:8px;padding:6px 10px;border-radius:8px;border:1px solid #d1d5db;cursor:pointer;'
        onclick="(async () => {{
          try {{
            const txt = {content_js};
            await navigator.clipboard.writeText(txt);
          }} catch (e) {{
            console.warn('Clipboard copy failed', e);
            alert('복사가 차단되었습니다. 수동 복사(Ctrl+C)해주세요.');
          }}
        }})()"
      >📋 복사</button>
    </div>
    """.replace("{content}", (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    # components.v1.html 은 key 파라미터를 받지 않는 환경이 있어 키 없이 호출
    comp_html(html_str, height=height + 110, scrolling=False)
