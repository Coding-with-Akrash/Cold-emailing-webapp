import json
import os
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class EmailLog:
    to_email: str
    company: str
    subject: str
    body: str
    sent_at: str
    status: str
    error: str = ""


@dataclass
class Campaign:
    name: str
    created_at: str
    description: str = ""
    total_targets: int = 0
    sent_count: int = 0
    failed_count: int = 0
    logs: List[EmailLog] = field(default_factory=list)


class Storage:
    def __init__(self, output_dir: str = "output", campaign_name: str = "default") -> None:
        self.output_dir = output_dir
        self.campaign_name = campaign_name
        os.makedirs(self.output_dir, exist_ok=True)
        self.campaign_path = os.path.join(self.output_dir, f"campaign_{campaign_name}.json")
        self.emails_path = os.path.join(self.output_dir, "emails.json")
        self._campaign = self._load_campaign()

    def _load_campaign(self) -> Campaign:
        if os.path.exists(self.campaign_path):
            with open(self.campaign_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logs = [EmailLog(**log) for log in data.get("logs", [])]
                data["logs"] = logs
                return Campaign(**data)
        return Campaign(
            name=self.campaign_name,
            created_at=datetime.now().isoformat(),
        )

    def save_campaign(self) -> None:
        data = asdict(self._campaign)
        with open(self.campaign_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def add_email_log(self, log: EmailLog) -> None:
        self._campaign.logs.append(log)
        if log.status == "sent":
            self._campaign.sent_count += 1
        elif log.status == "failed":
            self._campaign.failed_count += 1
        self.save_campaign()

    @property
    def campaign(self) -> Campaign:
        return self._campaign

    def get_stats(self) -> dict:
        return {
            "campaign_name": self._campaign.name,
            "total_sent": self._campaign.sent_count,
            "total_failed": self._campaign.failed_count,
            "total_targets": self._campaign.total_targets,
            "created_at": self._campaign.created_at,
        }

    def is_email_sent(self, to_email: str) -> bool:
        return any(log.to_email.lower() == to_email.lower() and log.status == "sent" for log in self._campaign.logs)

    def get_sent_emails(self) -> list:
        return [log.to_email.lower() for log in self._campaign.logs if log.status == "sent"]

    def has_any_sent_emails(self) -> bool:
        return any(log.status == "sent" for log in self._campaign.logs)
