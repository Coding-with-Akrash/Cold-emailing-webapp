import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserProfile:
    name: str = ""
    role: str = ""
    company: str = ""
    experience_years: str = ""
    skills: str = ""
    portfolio: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    achievements: str = ""
    notes: str = ""


@dataclass
class AppConfig:
    user: UserProfile = field(default_factory=UserProfile)
    openai_api_key: str = ""
    smtp_email: str = ""
    smtp_password: str = ""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    output_dir: str = "output"
    pdf_path: str = ""
    template_path: str = "templates"
    campaign_name: str = "default"

    def save(self, path: str = "config.json") -> None:
        data = {
            "user": {
                "name": self.user.name,
                "role": self.user.role,
                "company": self.user.company,
                "experience_years": self.user.experience_years,
                "skills": self.user.skills,
                "portfolio": self.user.portfolio,
                "phone": self.user.phone,
                "linkedin": self.user.linkedin,
                "github": self.user.github,
                "achievements": self.user.achievements,
                "notes": self.user.notes,
            },
            "openai_api_key": self.openai_api_key,
            "smtp_email": self.smtp_email,
            "smtp_password": self.smtp_password,
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "output_dir": self.output_dir,
            "pdf_path": self.pdf_path,
            "template_path": self.template_path,
            "campaign_name": self.campaign_name,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str = "config.json") -> "AppConfig":
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        user_data = data.get("user", {})
        return cls(
            user=UserProfile(**user_data),
            openai_api_key=data.get("openai_api_key", ""),
            smtp_email=data.get("smtp_email", ""),
            smtp_password=data.get("smtp_password", ""),
            smtp_server=data.get("smtp_server", "smtp.gmail.com"),
            smtp_port=data.get("smtp_port", 587),
            output_dir=data.get("output_dir", "output"),
            pdf_path=data.get("pdf_path", ""),
            template_path=data.get("template_path", "templates"),
            campaign_name=data.get("campaign_name", "default"),
        )
