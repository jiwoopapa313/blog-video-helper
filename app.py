def gen_youtube(topic, tone, n, mode):
    sys = (
        "You are a seasoned Korean YouTube scriptwriter for seniors. "
        "Return STRICT JSON only. "
        "Make EXACTLY N chapters (2–4 sentences each). "
        "Include image_prompts aligned 1:1 with chapters. "
        "Prompts must depict Korean seniors in Korean settings (avoid Western)."
    )

    # ⚠️ 중요: f-string에서 JSON 중괄호는 {{ }} 로 이스케이프
    user = f"""
[주제] {topic}
[톤] {tone}
[N] {n}
[유형] {('정보형' if mode == 'info' else '시공후기형(영업)')}

[JSON schema]
{{
  "titles": ["...", "...", "..."],
  "description": "(3~5줄 한국어)",
  "chapters": [
    {{"title":"Tip1","script":"..."}}
  ],
  "image_prompts": [
    {{"label":"Chap1","en":"...","ko":"..."}}
  ],
  "hashtags": ["#..", "#..", "#..", "#.."]
}}
- 'chapters'와 'image_prompts'는 길이 N으로 맞추고(1:1), 각 항목은 한국어 문장으로 작성.
- 정보형은 CTA(전화 문구) 금지. 영업형은 **앱이 설명 마지막 줄에 CTA를 자동 추가**합니다.
"""

    data = json_complete(sys, user, model_text, temperature)

    # 개수/정합성 보정
    chapters = data.get("chapters", [])[:n]
    prompts  = data.get("image_prompts", [])[:n]
    while len(chapters) < n:
        chapters.append({"title": f"Tip{len(chapters)+1}", "script": "간단한 보충 설명을 제공합니다."})
    while len(prompts) < n:
        i = len(prompts)
        prompts.append({"label": f"Chap{i+1}", "en": f"visual for chapter {i+1} of '{topic}'", "ko": f"챕터 {i+1} 보조 이미지"})
    data["chapters"] = chapters
    data["image_prompts"] = prompts

    # 선택: 후가공
    if polish:
        try:
            data = json.loads(
                chat(
                    "Polish Korean text for clarity; keep JSON shape and counts. RETURN JSON ONLY.",
                    json.dumps(data, ensure_ascii=False),
                    "gpt-4o",
                    0.4,
                )
            )
        except Exception:
            pass

    # 영업형: 설명 끝 CTA 보장(문자열 안에 파이썬식 넣지 말 것)
    if mode == "sales":
        desc = data.get("description", "").rstrip()
        if CTA not in desc:
            data["description"] = (desc + f"\n{CTA}").strip()

    return data
