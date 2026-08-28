# Cold-emailing-webapp

<div align="center">
  <p><strong>🎯 The Most Advanced AI-Powered Cold-emailing-webapp</strong></p>
  <p>Generate • Debug • Learn • Optimize</p>

  [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
  [![OpenAI GPT-4o-mini](https://img.shields.io/badge/GPT--4o--mini-powered-green.svg)](https://openai.com)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Stars](https://img.shields.io/github/stars/Coding-with-Akrash/Cold-emailing-webapp?style=social)](https://github.com/Coding-with-Akrash/Cold-emailing-webapp)
</div>
---
A Flask-based web application (with a CLI companion) for extracting emails from PDFs, generating personalized outreach emails with AI enhancement, and sending campaigns via SMTP.
---
## Features

- **PDF Extraction** - Extract company names and email addresses from PDF documents
- **Email Generation** - Generate personalized cold email drafts using configurable templates
- **AI Enhancement** - Optionally enhance emails with OpenAI GPT-4o for better personalization
- **SMTP Campaigns** - Send campaigns with automatic duplicate detection
- **Template Management** - Create, edit, and manage email templates
- **Stats & Logging** - Track sent, failed, and skipped emails per campaign
- **Web UI** - Clean Bootstrap-based dashboard interface
- **CLI** - Command-line interface for automation

## Project Structure

```
.
├── web_app.py          # Flask web application (main entry point for web)
├── main.py             # CLI entry point
├── config.py           # AppConfig / UserProfile dataclasses + JSON persistence
├── config.example.json # Template config (copy to config.json)
├── campaign.py         # EmailCampaign class (generation + sending logic)
├── storage.py          # Storage class (campaign persistence, email logs)
├── templates.py        # Email template engine (string.Template based)
├── openai_enhancer.py  # OpenAI API integration for email enhancement
├── pdf_reader.py       # PDF parsing and company/email extraction
├── requirements.txt    # Python dependencies
├── templates/          # Flask HTML templates + email .txt templates
└── .github/workflows/  # GitHub Actions CI
```

## Quick Start

### Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cold-emailing.git
   cd cold-emailing
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create config from example:
   ```bash
   cp config.example.json config.json
   ```

4. **Edit `config.json`** and add your real credentials:
   - `openai_api_key` - Your OpenAI API key (optional, for AI enhancement)
   - `smtp_email` - Your SMTP sender email
   - `smtp_password` - Your SMTP app password (e.g., Gmail App Password)

5. Run the web app:
   ```bash
   python web_app.py
   ```
   Or the CLI:
   ```bash
   python main.py --help
   ```

## Usage

### Web Interface

1. Start the server: `python web_app.py`
2. Open `http://localhost:5000`
3. Navigate to **Configuration** to set up your profile, API keys, and SMTP settings
4. Go to **Extract Emails** to upload a PDF and extract company data
5. Use **Generate** to create email drafts (with optional OpenAI enhancement)
6. Use **Send Campaign** to send emails via SMTP

### CLI

```bash
python main.py config      # Set up configuration interactively
python main.py extract     # Extract emails from PDF
python main.py generate    # Generate email drafts
python main.py send        # Send campaign
python main.py stats       # Show campaign statistics
```

## Configuration

All settings are stored in `config.json` (not committed - see `config.example.json`):

| Field | Description |
|-------|-------------|
| `user.*` | Your profile (name, role, skills, portfolio, etc.) |
| `openai_api_key` | OpenAI API key for AI-enhanced emails (optional) |
| `smtp_email` | Sender email address |
| `smtp_password` | SMTP password or app password |
| `smtp_server` | SMTP server (default: smtp.gmail.com) |
| `smtp_port` | SMTP port (default: 587) |
| `pdf_path` | Path to PDF for extraction |
| `campaign_name` | Campaign identifier for output files |
| `output_dir` | Directory for generated files (default: output) |

## Security

- **Never commit `config.json`** - It contains your API keys and SMTP credentials
- Use `.env` files or environment variables for production deployments
- The `SECRET_KEY` Flask session key can be set via the `SECRET_KEY` environment variable

## Deployment

### Deploy to Render

1. Fork this repository on GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Connect your GitHub repository
4. Set the build command: `pip install -r requirements.txt`
5. Set the start command: `python web_app.py`
6. Add environment variables for `openai_api_key`, `smtp_email`, `smtp_password`, and `SECRET_KEY`
7. Deploy!

### Deploy with GitHub Actions

A CI workflow is included at `.github/workflows/ci.yml` that runs on every push/PR to verify the code installs and lints correctly.

For deployment, add secrets to your GitHub repository:
- `OPENAI_API_KEY` - Your OpenAI API key
- `SMTP_EMAIL` - Your SMTP sender email
- `SMTP_PASSWORD` - Your SMTP app password
- `SECRET_KEY` - Flask secret key

## Dependencies

- `flask` - Web framework
- `pdfplumber` - PDF table/text extraction
- `openai` - OpenAI API client for AI enhancement
- `requests` - HTTP client

## License

MIT
