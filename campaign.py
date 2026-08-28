import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional

from pdf_reader import load_from_json
from templates import render_template
from openai_enhancer import enhance_with_openai, enhance_subject_line
from storage import Storage, EmailLog
from config import AppConfig, UserProfile


class EmailCampaign:
    def __init__(self, config: AppConfig, template_name: str = "default") -> None:
        self.config = config
        self.template_name = template_name
        self.storage = Storage(
            output_dir=config.output_dir,
            campaign_name=config.campaign_name,
        )
        self.records = []
        if os.path.exists("companies.json"):
            self.records = load_from_json("companies.json")

    def load_companies_from_pdf(self) -> List:
        from pdf_reader import build_company_records, save_to_json
        if not self.config.pdf_path or not os.path.exists(self.config.pdf_path):
            return []
        self.records = build_company_records(self.config.pdf_path)
        save_to_json(self.records, "companies.json")
        self.storage._campaign.total_targets = len(self.records)
        self.storage.save_campaign()
        return self.records

    def generate_emails(self, role: str = "Software Engineer", use_openai: bool = True, skip_sent: bool = True) -> List[dict]:
        user_vars = {
            "name": self.config.user.name or "Your Name",
            "role": role,
            "current_role": role,
            "company": "{company}",
            "experience_years": self.config.user.experience_years or "3",
            "skills": self.config.user.skills or "Python, JavaScript, React",
            "portfolio": self.config.user.portfolio or "https://yourportfolio.com",
            "linkedin": self.config.user.linkedin or "https://linkedin.com",
            "github": self.config.user.github or "https://github.com",
            "phone": self.config.user.phone or "+923001234567",
            "subject_line": f"Application for {role}",
            "custom_message": f"I am interested in exploring opportunities at your company.",
        }

        sent_email_set = set(self.storage.get_sent_emails()) if skip_sent else set()
        results = []
        skipped_duplicates = 0
        for rec in self.records:
            for email_addr in rec.emails:
                if skip_sent and email_addr.lower() in sent_email_set:
                    skipped_duplicates += 1
                    continue
                body = render_template(self.template_name, {
                    **user_vars,
                    "company": rec.company,
                })

                subject = f"Application for {role} at {rec.company}"

                if use_openai and self.config.openai_api_key:
                    enhanced_body = enhance_with_openai(
                        api_key=self.config.openai_api_key,
                        company=rec.company,
                        role=role,
                        base_text=body,
                        user_profile={
                            "name": self.config.user.name,
                            "skills": self.config.user.skills,
                            "experience_years": self.config.user.experience_years,
                            "achievements": self.config.user.achievements,
                            "portfolio": self.config.user.portfolio,
                            "linkedin": self.config.user.linkedin,
                        },
                    )
                    enhanced_subject = enhance_subject_line(
                        api_key=self.config.openai_api_key,
                        company=rec.company,
                        role=role,
                    )
                    subject = enhanced_subject
                    body = enhanced_body

                results.append({
                    "to": email_addr,
                    "company": rec.company,
                    "subject": subject,
                    "body": body,
                    "skipped_duplicate": False,
                })
        return results, skipped_duplicates

    def save_drafts(self, drafts: List[dict]) -> str:
        import csv
        path = os.path.join(self.config.output_dir, f"drafts_{self.config.campaign_name}.csv")
        os.makedirs(self.config.output_dir, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["To", "Company", "Subject", "Body"])
            for d in drafts:
                writer.writerow([d["to"], d["company"], d["subject"], d["body"]])
        return path

    def send_email(self, to_email: str, subject: str, body: str) -> tuple:
        if not self.config.smtp_email or not self.config.smtp_password:
            return ("skipped", "SMTP credentials not configured")

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_email, self.config.smtp_password)
                server.send_message(msg)

            log = EmailLog(
                to_email=to_email,
                company="",
                subject=subject,
                body=body,
                sent_at=datetime.now().isoformat(),
                status="sent",
            )
            self.storage.add_email_log(log)
            return ("sent", "Email sent successfully")
        except Exception as e:
            log = EmailLog(
                to_email=to_email,
                company="",
                subject=subject,
                body=body,
                sent_at=datetime.now().isoformat(),
                status="failed",
                error=str(e),
            )
            self.storage.add_email_log(log)
            return ("failed", str(e))

    def run_campaign(self, role: str = "Software Engineer", use_openai: bool = True, dry_run: bool = True, skip_sent: bool = True) -> dict:
        if not self.records:
            self.load_companies_from_pdf()

        drafts, skipped_duplicates = self.generate_emails(role=role, use_openai=use_openai, skip_sent=skip_sent)
        self.storage._campaign.total_targets = len(drafts) + skipped_duplicates
        self.storage.save_campaign()

        results = {"drafted": 0, "sent": 0, "failed": 0, "skipped": 0, "duplicates_skipped": skipped_duplicates, "drafts": []}

        if dry_run:
            csv_path = self.save_drafts(drafts)
            results["drafted"] = len(drafts)
            results["drafts_path"] = csv_path
            results["message"] = f"Dry run complete. {len(drafts)} drafts saved to {csv_path}."
            if skipped_duplicates:
                results["message"] += f" {skipped_duplicates} duplicates skipped (already sent)."
            for d in drafts:
                results["drafts"].append({
                    "to": d["to"],
                    "company": d["company"],
                    "subject": d["subject"],
                    "body": d["body"],
                    "status": "draft",
                })
            return results

        sent_email_set = set(self.storage.get_sent_emails()) if skip_sent else set()
        for draft in drafts:
            if skip_sent and draft["to"].lower() in sent_email_set:
                results["skipped"] += 1
                results["drafts"].append({
                    "to": draft["to"],
                    "company": draft["company"],
                    "subject": draft["subject"],
                    "status": "skipped",
                    "message": "Already sent in previous campaign",
                })
                continue
            status, msg = self.send_email(draft["to"], draft["subject"], draft["body"])
            if status == "sent":
                results["sent"] += 1
            elif status == "failed":
                results["failed"] += 1
            else:
                results["skipped"] += 1
            results["drafts"].append({
                "to": draft["to"],
                "company": draft["company"],
                "subject": draft["subject"],
                "status": status,
                "message": msg,
            })

        results["message"] = f"Campaign complete. Sent: {results['sent']}, Failed: {results['failed']}, Skipped: {results['skipped']}"
        if skipped_duplicates:
            results["message"] += f" (Duplicates skipped before send: {skipped_duplicates})"
        return results
