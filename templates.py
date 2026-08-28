from pathlib import Path
from string import Template
from typing import Dict


TEMPLATES_DIR = Path("templates")


def ensure_templates_dir() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def get_builtin_templates() -> Dict[str, str]:
    return {
        "default": """Subject: Application for ${role} Position

Dear Hiring Manager,

I hope this email finds you well. I am writing to express my interest in joining ${company} as a ${role}.

With over ${experience_years} years of experience in ${skills}, I am confident that I can contribute effectively to your team. Currently, I am working as a ${current_role} and have been actively looking for new opportunities in Lahore.

Here are my key details:
- Resume/Portfolio: ${portfolio}
- LinkedIn: ${linkedin}
- GitHub: ${github}
- Contact: ${phone}

I would welcome the opportunity to discuss how my background aligns with ${company}'s goals. Please find my attached resume and portfolio for your review.

Thank you for your time and consideration.

Best regards,
${name}
""",
        "software_engineer": """Subject: Experienced Software Engineer - ${name}

Hi ${company} Team,

I am a passionate software engineer with ${experience_years} years of experience building scalable applications using ${skills}. I am reaching out to explore potential opportunities at ${company}.

About me:
- Designation: ${role}
- Key Skills: ${skills}
- Portfolio: ${portfolio}
- LinkedIn: ${linkedin}

I am particularly excited about ${company}'s work and would love to contribute to your engineering team.

Looking forward to hearing from you.

Best,
${name}
Phone: ${phone}
""",
        "custom": """Subject: ${subject_line}

Dear ${company} Team,

${custom_message}

--
${name}
${role}
${phone}
${linkedin}
${portfolio}
""",
    }


def save_builtin_templates() -> None:
    ensure_templates_dir()
    templates = get_builtin_templates()
    for name, content in templates.items():
        path = TEMPLATES_DIR / f"{name}.txt"
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return get_builtin_templates().get(name, get_builtin_templates()["default"])


def list_templates() -> list:
    ensure_templates_dir()
    save_builtin_templates()
    return [p.stem for p in TEMPLATES_DIR.glob("*.txt")]


def render_template(template_name: str, variables: Dict[str, str]) -> str:
    raw = load_template(template_name)
    tpl = Template(raw)
    defaults = {
        "name": "Your Name",
        "role": "Software Engineer",
        "current_role": "Software Engineer",
        "company": "the company",
        "experience_years": "3",
        "skills": "Python, JavaScript, React, Node.js",
        "portfolio": "https://yourportfolio.com",
        "linkedin": "https://linkedin.com/in/yourprofile",
        "github": "https://github.com/yourusername",
        "phone": "+923001234567",
        "subject_line": "Experienced Software Engineer Looking for Opportunities",
        "custom_message": "I am reaching out to explore potential opportunities at your company.",
    }
    defaults.update(variables)
    try:
        return tpl.safe_substitute(defaults)
    except Exception as e:
        return f"Template Error: {e}"
