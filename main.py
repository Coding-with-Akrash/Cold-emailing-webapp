#!/usr/bin/env python3
"""Cold Emailing System - CLI Entry Point"""

import argparse
import sys
import os
import json

from config import AppConfig, UserProfile
from pdf_reader import build_company_records, save_to_csv, save_to_json, load_from_json
from templates import list_templates, render_template, get_builtin_templates, save_builtin_templates
from campaign import EmailCampaign
from storage import Storage


def print_header(text: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def setup_config(args) -> AppConfig:
    config = AppConfig.load()
    print_header("CONFIGURATION SETUP")
    print("Fill in your details (press Enter to keep default/saved value)")

    def prompt(field_name: str, current_val: str, mask: bool = False) -> str:
        prompt_text = f"{field_name} [{current_val}]: " if current_val else f"{field_name}: "
        val = input(prompt_text)
        return val if val else current_val

    print("\n--- User Profile ---")
    config.user.name = prompt("Full Name", config.user.name)
    config.user.role = prompt("Role/Designation", config.user.role)
    config.user.company = prompt("Company (if employed)", config.user.company)
    config.user.experience_years = prompt("Years of Experience", config.user.experience_years)
    print("Skills (comma separated):", end=" ")
    skills = input(f" [{config.user.skills}]: ")
    config.user.skills = skills if skills else config.user.skills
    config.user.portfolio = prompt("Portfolio URL", config.user.portfolio)
    config.user.phone = prompt("Phone Number", config.user.phone)
    config.user.linkedin = prompt("LinkedIn URL", config.user.linkedin)
    config.user.github = prompt("GitHub URL", config.user.github)
    config.user.achievements = prompt("Key Achievements", config.user.achievements)

    print("\n--- API & SMTP Settings ---")
    config.openai_api_key = prompt("OpenAI API Key", config.openai_api_key)
    config.smtp_email = prompt("SMTP Email (sender)", config.smtp_email)
    config.smtp_password = prompt("SMTP Password/App Password", config.smtp_password, mask=True)
    config.pdf_path = prompt("PDF file path", config.pdf_path)
    config.campaign_name = prompt("Campaign Name", config.campaign_name)

    config.save()
    print("\nConfiguration saved to config.json")
    return config


def cmd_config(args) -> int:
    config = setup_config(args)
    return 0


def cmd_extract(args) -> int:
    print_header("PDF EMAIL EXTRACTION")
    pdf_path = args.pdf or "Software Houses In Lahore.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return 1

    records = build_company_records(pdf_path)
    save_to_json(records, "companies.json")
    save_to_csv(records, "companies.csv")

    print(f"Extracted {len(records)} companies from {pdf_path}")
    emails_found = sum(len(r.emails) for r in records)
    print(f"Total emails found: {emails_found}")
    print(f"\nFirst 10 companies:")
    for r in records[:10]:
        print(f"  - {r.company}: {', '.join(r.emails) if r.emails else 'No email'}")
    print(f"\nSaved to companies.json and companies.csv")
    return 0


def cmd_list_templates(args) -> int:
    print_header("AVAILABLE EMAIL TEMPLATES")
    templates = list_templates()
    for t in templates:
        print(f"  - {t}")
    print()
    return 0


def cmd_show_template(args) -> int:
    name = args.name if args.name else "default"
    content = render_template(name, {})
    print_header(f"TEMPLATE: {name}")
    print(content)
    return 0


def cmd_generate(args) -> int:
    print_header("EMAIL GENERATION")
    config = AppConfig.load()
    if not config.pdf_path and os.path.exists("companies.json"):
        config.pdf_path = "Software Houses In Lahore.pdf"

    campaign = EmailCampaign(config, template_name=args.template or "default")
    use_openai = args.no_openai is False

    if args.role:
        role = args.role
    else:
        role = config.user.role or "Software Engineer"

    results = campaign.run_campaign(
        role=role,
        use_openai=use_openai,
        dry_run=True,
    )

    print(f"Generated {results['drafted']} email drafts")
    if "drafts_path" in results:
        print(f"Drafts saved to: {results['drafts_path']}")
    print(results.get("message", ""))

    if args.preview:
        print_header("SAMPLE DRAFT")
        sample_count = min(3, len(results.get("drafts", [])))
        for i in range(sample_count):
            d = results["drafts"][i]
            print(f"\n--- To: {d['to']} | Company: {d['company']} ---")
            print(f"Subject: {d['subject']}")
            print(f"Body:\n{d['body'][:500]}")
    return 0


def cmd_send(args) -> int:
    print_header("SENDING CAMPAIGN")
    config = AppConfig.load()

    if not config.smtp_email or not config.smtp_password:
        print("ERROR: SMTP credentials not configured. Run 'python main.py config' first.")
        return 1

    if not config.openai_api_key:
        print("WARNING: OpenAI API key not set. Emails will use template without AI enhancement.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return 0

    campaign = EmailCampaign(config, template_name=args.template or "default")
    role = args.role or config.user.role or "Software Engineer"

    results = campaign.run_campaign(
        role=role,
        use_openai=True,
        dry_run=False,
    )

    print_header("CAMPAIGN RESULTS")
    print(f"Sent: {results['sent']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped: {results['skipped']}")
    print(results.get("message", ""))
    return 0


def cmd_stats(args) -> int:
    print_header("CAMPAIGN STATS")
    storage = Storage()
    stats = storage.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    return 0


def cmd_create_template(args) -> int:
    from templates import TEMPLATES_DIR
    name = args.name
    if not name:
        print("Error: --name is required")
        return 1
    path = TEMPLATES_DIR / f"{name}.txt"
    if path.exists():
        overwrite = input(f"Template '{name}' already exists. Overwrite? (y/N): ")
        if overwrite.lower() != "y":
            print("Cancelled.")
            return 0

    print(f"Creating template '{name}'. Enter the email body.")
    print("Available placeholders: ${name}, ${role}, ${company}, ${experience_years}, ${skills}, ${portfolio}, ${linkedin}, ${github}, ${phone}, ${subject_line}, ${custom_message}")
    print("Press Ctrl+Z then Enter when done (or type END on a new line):")
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Template '{name}' saved to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coldemail",
        description="Cold Emailing System - Extract emails from PDFs and automate personalized outreach",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    p_config = subparsers.add_parser("config", help="Setup/update configuration")
    p_config.add_argument("--set", action="store_true", help="Run interactive setup")

    p_extract = subparsers.add_parser("extract", help="Extract emails from PDF")
    p_extract.add_argument("--pdf", help="Path to PDF file")

    p_templates = subparsers.add_parser("templates", help="List available templates")

    p_show = subparsers.add_parser("show-template", help="Show a template")
    p_show.add_argument("--name", help="Template name")

    p_generate = subparsers.add_parser("generate", help="Generate email drafts")
    p_generate.add_argument("--role", help="Role/designation")
    p_generate.add_argument("--template", help="Template name")
    p_generate.add_argument("--no-openai", action="store_true", help="Disable OpenAI enhancement")
    p_generate.add_argument("--preview", action="store_true", help="Preview a few drafts")

    p_send = subparsers.add_parser("send", help="Send campaign emails")
    p_send.add_argument("--role", help="Role/designation")
    p_send.add_argument("--template", help="Template name")

    p_stats = subparsers.add_parser("stats", help="Show campaign stats")

    p_create = subparsers.add_parser("create-template", help="Create a new email template")
    p_create.add_argument("--name", required=True, help="Template name")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    handlers = {
        "config": cmd_config,
        "extract": cmd_extract,
        "templates": cmd_list_templates,
        "show-template": cmd_show_template,
        "generate": cmd_generate,
        "send": cmd_send,
        "stats": cmd_stats,
        "create-template": cmd_create_template,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
