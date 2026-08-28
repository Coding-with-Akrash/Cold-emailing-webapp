import re
import csv
import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CompanyRecord:
    company: str
    website: str
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    location: str = "Lahore"
    source_pdf: str = ""
    contacted: bool = False
    contact_date: str = ""


def extract_emails_from_text(text: str) -> List[str]:
    pattern = r"[\w\.-]+@[\w\.-]+\.\w{2,}"
    found = re.findall(pattern, text, re.IGNORECASE)
    cleaned = []
    for email in found:
        email = email.strip().rstrip(".")
        if email not in cleaned:
            cleaned.append(email)
    return cleaned


def extract_phones_from_text(text: str) -> List[str]:
    pattern = r"\+?92\d{9}|\+?1\d{10}|\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4}"
    found = re.findall(pattern, text)
    return list(set(found))


def parse_pdf_tables(pdf_path: str) -> List[Dict]:
    import pdfplumber
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cleaned = [cell.strip() for cell in row if cell and cell.strip()]
                    if len(cleaned) >= 3:
                        records.append({
                            "company": cleaned[0],
                            "website": cleaned[1] if len(cleaned) > 1 else "",
                            "contact_raw": cleaned[2] if len(cleaned) > 2 else "",
                        })
            text = page.extract_text() or ""
            lines = text.split("\n")
            for line in lines:
                parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
                if len(parts) >= 3 and parts[0] not in ("COMPANY", "WEBSITE", "CONTACT"):
                    records.append({
                        "company": parts[0],
                        "website": parts[1] if len(parts) > 1 else "",
                        "contact_raw": parts[2] if len(parts) > 2 else "",
                    })
    return records


def build_company_records(pdf_path: str) -> List[CompanyRecord]:
    raw_records = parse_pdf_tables(pdf_path)
    companies = {}
    for rec in raw_records:
        name = rec.get("company", "").strip()
        if not name or "COMPANY" in name or "WEBSITE" in name or "CONTACT" in name:
            continue
        if name not in companies:
            companies[name] = CompanyRecord(
                company=name,
                website=rec.get("website", ""),
                source_pdf=os.path.basename(pdf_path),
            )
        contact_raw = rec.get("contact_raw", "")
        emails = extract_emails_from_text(contact_raw)
        phones = extract_phones_from_text(contact_raw)
        for email in emails:
            if email not in companies[name].emails:
                companies[name].emails.append(email)
        for phone in phones:
            if phone not in companies[name].phones:
                companies[name].phones.append(phone)
    return list(companies.values())


def save_to_csv(records: List[CompanyRecord], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Company", "Website", "Emails", "Phones", "Location", "Contacted", "Contact Date"])
        for r in records:
            writer.writerow([
                r.company, r.website, ";".join(r.emails), ";".join(r.phones),
                r.location, r.contacted, r.contact_date,
            ])


def save_to_json(records: List[CompanyRecord], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = [asdict(r) for r in records]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_from_json(path: str) -> List[CompanyRecord]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [CompanyRecord(**item) for item in data]
