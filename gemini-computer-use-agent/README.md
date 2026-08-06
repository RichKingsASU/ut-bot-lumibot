# Gemini Computer Use Agent (`gemini-computer-use-agent`)

An autonomous browser automation agent powered by **Google's Gemini Computer Use API** (Interactions API with `gemini-3.6-flash`).

The agent observes browser state via real-time Playwright screenshots, translates 0–999 normalized visual coordinates into actual pixel coordinates, executes mouse/keyboard UI actions, enforces Human-in-the-Loop safety confirmation, and records structured audit logs.

---

## Key Features

1. **Interactions API Integration**: Uses `google-genai` SDK (`client.interactions.create`) with `previous_interaction_id` stateful conversation tracking.
2. **Playwright Execution Environment**: Launches a sandboxed Chromium session with fixed `1440x900` resolution viewport.
3. **Full UI Action Support**: Supports all Gemini Computer Use predefined actions (`click_at`, `type_text_at`, `hover_at`, `scroll_document`, `scroll_at`, `drag_and_drop`, `key_combination`, `navigate`, `go_back`, `go_forward`, `search`, `wait_5_seconds`).
4. **Human-in-the-Loop (HITL) Safety**:
   - Evaluates `safety_decision` responses from Google's safety service.
   - Enforces system instruction policies asking for explicit CLI user approval before taking high-stakes actions (legal agreements, financial transactions, CAPTCHAs, sensitive personal data, downloads, messaging, account login).
   - Sends `safety_acknowledgement: True` back to the model upon user approval.
5. **Domain Allowlist & Blocklist**: Validates all navigation targets against security rule sets before performing page loads.
6. **Structured Audit Logging**: Logs every prompt, screenshot file, suggested model action, safety prompt decision, and execution duration to `logs/audit.jsonl` and `logs/screenshots/`.

---

## Project Structure

```
gemini-computer-use-agent/
├── README.md               # Documentation and usage guide
├── requirements.txt        # Python package dependencies
├── setup.sh                # Automated setup script
├── config.py               # Settings and Pydantic configuration models
├── logging_utils.py        # Audit logger and colorized terminal output
├── safety.py               # System instruction & Human-in-the-Loop safety manager
├── browser_env.py          # Playwright browser manager, coordinate scaler, & action executor
├── agent_loop.py           # Computer use interaction loop
├── main.py                 # CLI entry point
└── tests/
    └── test_agent.py       # Unit tests
```

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10+
- A valid Gemini API Key (`GEMINI_API_KEY`)

### 2. Run Setup Script
```bash
chmod +x setup.sh
./setup.sh
```

Or manually install:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Set Environment Variable
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## Usage Examples

### 1. Run Default Task
```bash
python3 main.py "Navigate to google.com and search for Gemini API"
```

### 2. Headful Mode (Visible Browser Window)
```bash
python3 main.py "Search for weather in Tokyo on Google" --headful
```

### 3. Specify Target Model and Max Turns
```bash
python3 main.py "Find pricing for Google Cloud Run" --model gemini-3.6-flash --max-turns 15
```

### 4. Domain Restrictions (Allowlist / Blocklist)
```bash
python3 main.py "Search for news on Wikipedia" --allowlist wikipedia.org,google.com --blocklist malicious.com
```

---

## Safety Policy & Confirmation Categories

The agent enforces a multi-layered safety strategy:
- **Prompt Injection Detection**: `enable_prompt_injection_detection=True` is passed with the `computer_use` tool config.
- **Rule 1 (User Confirmation)**: The agent pauses and prompts the user via terminal before:
  - Accepting Terms of Service / Cookie Banners / EULAs
  - Attempting CAPTCHAs or robot verification
  - Financial transactions or checkout completion
  - Sending emails or social media messages
  - Accessing sensitive health/financial/personal identifiers
  - Downloading files or sharing user data
  - Logging into accounts

---

## Audit Logs

All agent interactions and screenshot artifacts are stored under the log directory (`logs/` by default):
- `logs/audit.jsonl`: Line-delimited JSON log of prompts, model intents, safety decisions, actions, and timings.
- `logs/screenshots/`: Captured PNG screenshots for each interaction turn (`turn_0_...png`, `turn_1_...png`, etc.).
