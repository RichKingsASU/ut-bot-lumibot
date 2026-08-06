"""Safety policy enforcement and Human-in-the-Loop (HITL) module for Gemini Computer Use Agent."""

from typing import Any, Dict, Tuple
import termcolor
from logging_utils import AuditLogger

# Comprehensive System Instruction enforcing strict user confirmation for high-stakes actions
SYSTEM_SAFETY_INSTRUCTION = """## **RULE 1: Seek User Confirmation (USER_CONFIRMATION)**

This is your first and most important check. If the next required action falls into any of the following categories, you MUST stop immediately, and seek the user's explicit permission before taking the action.

**Procedure for Seeking Confirmation:**
* **For Consequential Actions:** Perform all preparatory steps (e.g., navigating, filling out forms, typing a message). You will ask for confirmation **AFTER** all necessary information is entered on the screen, but **BEFORE** you perform the final, irreversible action (e.g., before clicking "Send", "Submit", "Confirm Purchase", "Share").
* **For Prohibited Actions:** If the action is strictly forbidden (e.g., accepting legal terms, solving a CAPTCHA), you must first inform the user about the required action and ask for their confirmation to proceed.

**USER_CONFIRMATION Categories:**

* **Consent and Agreements:** You are FORBIDDEN from accepting, selecting, or agreeing to any of the following on the user's behalf. You must ask the user to confirm before performing these actions:
    - Terms of Service
    - Privacy Policies
    - Cookie consent banners
    - End User License Agreements (EULAs)
    - Any other legally significant contracts or agreements.
* **Robot Detection:** You MUST NEVER attempt to solve or bypass CAPTCHAs or human verification mechanisms without user confirmation.
* **Financial Transactions:** Completing purchases, money transfers, or financial transactions.
* **Sending Communications:** Sending emails, posting on social media/forums, or sending instant messages.
* **Accessing or Modifying Sensitive Information:** Health, financial, government records, SSN, passwords, or personal identifiers.
* **User Data Management:** Downloading files, transferring user data, or sharing files with third parties.
* **Browser Data & Identity:** Accessing browser history/passwords, or logging into any user account.

---

## **RULE 2: Default Behavior (ACTUATE)**

If an action does **NOT** fall under the conditions for `USER_CONFIRMATION`, your default behavior is to **Actuate** (proactively perform all necessary steps to move the user's request forward).
"""


class SafetyManager:
    """Manages safety checks and Human-in-the-Loop CLI interactions."""

    def __init__(self, logger: AuditLogger):
        self.logger = logger

    def process_safety_decision(
        self, safety_decision: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """Evaluates a safety decision attached to a model function_call.

        Returns:
            Tuple of (status, acknowledged), where status is 'CONTINUE', 'HALT', or 'SKIP',
            and acknowledged is True if user confirmed.
        """
        decision_type = safety_decision.get("decision", "").lower()
        explanation = safety_decision.get(
            "explanation", "Action requires human approval."
        )

        if decision_type == "blocked":
            termcolor.cprint(
                f"\n[SAFETY BLOCKED] Action blocked by safety service: {explanation}",
                color="red",
                attrs=["bold"],
            )
            self.logger.log_safety_prompt(explanation, "BLOCKED")
            return ("HALT", False)

        if decision_type == "require_confirmation":
            termcolor.cprint(
                "\n⚠️  [SAFETY CONFIRMATION REQUIRED]", color="yellow", attrs=["bold"]
            )
            termcolor.cprint(f"Explanation: {explanation}", color="yellow")

            user_input = ""
            while user_input.lower() not in ("y", "n", "yes", "no"):
                try:
                    user_input = input("Do you approve executing this action? [Y]es/[N]o: ")
                except (EOFError, KeyboardInterrupt):
                    user_input = "no"

            if user_input.lower() in ("y", "yes"):
                self.logger.log_safety_prompt(explanation, "CONTINUE")
                return ("CONTINUE", True)
            else:
                self.logger.log_safety_prompt(explanation, "DENIED")
                termcolor.cprint("User denied action confirmation.", color="red")
                return ("HALT", False)

        # Regular / allowed action
        return ("CONTINUE", False)
