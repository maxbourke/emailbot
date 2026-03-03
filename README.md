# EmailBot

A minimal email automation tool that generates personalized emails using AI and sends them via Gmail SMTP.

## What it does

EmailBot reads contact lists, applies business rules to determine who should be emailed, generates personalized email content using OpenRouter AI models, and either previews or sends emails via Gmail SMTP.

Features:
- AI-generated personalized email content via OpenRouter
- Contact filtering based on business rules and last contact dates
- Safe dry-run mode (default) with email previews
- Real email sending via Gmail SMTP
- Professional signatures with unsubscribe compliance
- CSV-based contact management
- YAML-based configuration
- Built-in rate limiting and retry logic

## Setup

### 1. Run with uv (recommended)

EmailBot uses uv for dependency management. No virtual environment setup required:

```bash
uv run email_bot.py --help
```

### 2. Alternative: Traditional setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up API keys

**OpenRouter API**: Get an API key from [OpenRouter.ai](https://openrouter.ai)
```bash
export OPENROUTER_API_KEY="your_api_key_here"
```

**Gmail SMTP**: Set up Gmail credentials for email sending
```bash
export GMAIL_USERNAME="your_gmail@gmail.com"
export GMAIL_APP_PASSWORD="your_16_character_app_password"
```

To get a Gmail App Password:
1. Go to Google Account settings → Security → 2-Step Verification
2. Generate an App Password for "EmailBot"
3. Use the 16-character password (not your regular Gmail password)

Add to your `~/.zshrc` or `~/.bash_profile` to make persistent:
```bash
echo 'export OPENROUTER_API_KEY="your_api_key"' >> ~/.zshrc
echo 'export GMAIL_USERNAME="your_gmail@gmail.com"' >> ~/.zshrc
echo 'export GMAIL_APP_PASSWORD="your_app_password"' >> ~/.zshrc
source ~/.zshrc
```

## Usage

### Dry run (safe preview mode - default)

```bash
uv run email_bot.py \
    --contacts contacts.csv \
    --rules rules.yaml \
    --company company.yaml \
    --campaign campaign.txt \
    --dry-run
```

This will:
- Show which contacts will be emailed and why others are skipped
- Generate and preview email content
- Save emails as `.eml` files in timestamped `Test_Outputs/` directory
- **Not send any actual emails**

### Real sending

```bash
uv run email_bot.py \
    --contacts contacts.csv \
    --rules rules.yaml \
    --company company.yaml \
    --campaign campaign.txt \
    --send
```

This will send emails via Gmail SMTP with a 5-second delay between sends.

### Skip confirmation

```bash
uv run email_bot.py \
    --contacts contacts.csv \
    --rules rules.yaml \
    --company company.yaml \
    --campaign campaign.txt \
    --send --yes
```

Use `--yes` or `-y` to skip the confirmation prompt when sending.

## Configuration Files

- **`contacts.csv`**: Contact list with email, type, and last contact date
- **`rules.yaml`**: OpenRouter config and minimum email intervals per contact type  
- **`company.yaml`**: Company information, email settings, and SMTP configuration
- **`campaign.txt`**: Plain text campaign description for AI to personalize
- **`signatures/default.txt`**: Email signature template with unsubscribe info

## Important Notes

### Mock Email Addresses

All provided contacts use `@example.com` email addresses with a common token `XQF7M` for easy identification:
- Format: `first.last.XQF7M@example.com`
- This allows you to search and mass-delete test emails later

### Gmail SMTP Configuration

The tool uses Gmail SMTP for reliable email delivery. Benefits:
- **Actually reaches recipients** (unlike macOS mail command)
- **Proper authentication** with TLS encryption
- **Professional headers** and MIME formatting
- **Rate limiting** with automatic retries

### OpenRouter Models

The default model is `google/gemini-2.5-flash-lite`. You can change this in `rules.yaml`. See [OpenRouter's model list](https://openrouter.ai/models) for available options.

### Email Compliance

All emails include:
- Professional signature with contact information
- Clear testing disclaimer
- Unsubscribe instructions
- Proper Australian English tone

## File Structure

```
emailbot/
├── email_bot.py              # Main CLI tool with uv dependencies
├── contacts.csv               # Full contact database (10 contacts)
├── contacts_single.csv        # Single contact for testing
├── rules.yaml                 # Business rules and AI config
├── company.yaml               # Company context and SMTP settings
├── campaign.txt               # Campaign description
├── signatures/
│   └── default.txt           # Email signature template
├── Test_Outputs/             # Timestamped dry-run outputs
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── CLAUDE.md                 # Development notes and technical details
```

## Example Company: Aqua Harbour Pools & Spas

The tool comes configured with a realistic Australian pool company:
- **Location**: Sydney, NSW
- **Services**: Custom pools, spas, saltwater systems
- **Campaign**: AquaLux 8x5 pool launch for summer 2027
- **Tone**: Professional but warm Australian voice

## Troubleshooting

1. **API Key Issues**: Make sure both `OPENROUTER_API_KEY` and Gmail credentials are set
2. **Gmail Authentication**: Use App Password, not regular Gmail password
3. **Permission Issues**: Tool creates `Test_Outputs/` directory for dry-run files
4. **Date Format Issues**: Ensure `last_contacted` dates in CSV are ISO format (YYYY-MM-DD)
5. **Rate Limiting**: Tool handles OpenRouter rate limits with automatic retries

## Safety Features

- **Dry-run by default**: Prevents accidental sending
- **Confirmation prompt**: Real sending mode asks for confirmation (use `--yes` to bypass)
- **Delay between sends**: 5-second delays prevent mail server issues
- **Mock domains**: All test data uses @example.com to avoid real addresses
- **Testing disclaimers**: Clear warnings that emails are for testing only
- **Unsubscribe compliance**: All emails include unsubscribe instructions

## Gmail Sending Limits

- **Free Gmail**: 500 emails per day
- **Google Workspace**: 2,000 emails per day
- **Current setup**: Suitable for small-scale campaigns
- **For larger campaigns**: Consider dedicated email marketing platforms