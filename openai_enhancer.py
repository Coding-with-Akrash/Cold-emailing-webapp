from typing import Dict


def enhance_with_openai(api_key: str, company: str, role: str, base_text: str, user_profile: dict) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        return base_text + "\n\n[Note: openai package not installed. Run: pip install openai]"

    system_prompt = (
        "You are an expert cold-email copywriter for job seekers. "
        "Your task is to rewrite the given email draft to be more personalized, concise, and compelling. "
        "Keep it professional, mention the company name naturally, highlight the candidate's key skills, "
        "and include a clear call-to-action. Do not make it sound generic or like spam. "
        "Return ONLY the improved email body (no subject line, no extra commentary)."
    )

    context = (
        f"Candidate Name: {user_profile.get('name', 'Your Name')}\n"
        f"Role Applying For: {role}\n"
        f"Target Company: {company}\n"
        f"Skills: {user_profile.get('skills', 'N/A')}\n"
        f"Experience: {user_profile.get('experience_years', 'N/A')} years\n"
        f"Achievements: {user_profile.get('achievements', 'N/A')}\n"
        f"Portfolio: {user_profile.get('portfolio', 'N/A')}\n"
        f"LinkedIn: {user_profile.get('linkedin', 'N/A')}\n\n"
        f"Original Draft:\n{base_text}\n\n"
        f"Rewrite this email to be more engaging and personalized for {company}. "
        f"Mention the company name, their likely technical focus, and the candidate's relevant skills. "
        f"Keep it under 200 words."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        improved = response.choices[0].message.content.strip()
        return improved if improved else base_text
    except Exception as e:
        return base_text + f"\n\n[OpenAI Enhancement Error: {str(e)}]"


def enhance_subject_line(api_key: str, company: str, role: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        return f"Application for {role} at {company}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Create a concise, professional cold email subject line for a job application. Return ONLY the subject line text, nothing else. Keep it under 10 words."},
                {"role": "user", "content": f"Company: {company}, Role: {role}, Candidate: software engineer with relevant skills."},
            ],
            max_tokens=50,
            temperature=0.5,
        )
        subject = response.choices[0].message.content.strip()
        subject = subject.strip("\"'")
        return subject
    except Exception:
        return f"Experienced Engineer - {role} Opportunity at {company}"
