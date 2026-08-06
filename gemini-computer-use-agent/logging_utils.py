"""Structured audit logging for Gemini Computer Use Agent."""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import termcolor


class AuditLogger:
    """Logs prompts, screenshots, model actions, safety decisions, and action execution results."""

    def __init__(self, log_dir: str = "logs", screenshots_dir: str = "logs/screenshots"):
        self.log_dir = log_dir
        self.screenshots_dir = screenshots_dir
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.log_dir, "audit.jsonl")

    def _append_log(self, event_type: str, data: Dict[str, Any]) -> None:
        """Appends a structured JSON object to the audit log file."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def save_screenshot(self, screenshot_bytes: bytes, turn_index: int) -> str:
        """Saves screenshot bytes to the screenshots directory and returns the filepath."""
        timestamp = int(time.time())
        filename = f"turn_{turn_index}_{timestamp}.png"
        filepath = os.path.join(self.screenshots_dir, filename)
        with open(filepath, "wb") as f:
            f.write(screenshot_bytes)
        self._append_log("screenshot_saved", {"turn": turn_index, "filepath": filepath, "size": len(screenshot_bytes)})
        return filepath

    def log_user_prompt(self, prompt: str, initial_url: str) -> None:
        """Logs initial user task and starting URL."""
        termcolor.cprint(f"\n[TASK] {prompt}", color="cyan", attrs=["bold"])
        termcolor.cprint(f"[START URL] {initial_url}", color="cyan")
        self._append_log("user_prompt", {"prompt": prompt, "initial_url": initial_url})

    def log_model_thought(self, text: str) -> None:
        """Logs model explanation or thought process."""
        termcolor.cprint(f"[MODEL INTENT] {text}", color="magenta")
        self._append_log("model_thought", {"text": text})

    def log_suggested_action(self, fname: str, args: Dict[str, Any], safety_decision: Optional[Dict[str, Any]] = None) -> None:
        """Logs an action proposed by the model."""
        termcolor.cprint(f"  -> Proposed Action: {fname} {args}", color="blue")
        if safety_decision:
            termcolor.cprint(f"     Safety Decision: {safety_decision.get('decision')} - {safety_decision.get('explanation')}", color="yellow")
        self._append_log("suggested_action", {"name": fname, "arguments": args, "safety_decision": safety_decision})

    def log_safety_prompt(self, explanation: str, result: str) -> None:
        """Logs a Human-in-the-loop safety prompt and user decision."""
        color = "green" if result == "CONTINUE" else "red"
        termcolor.cprint(f"[SAFETY HITL] Decision: {result} for explanation: '{explanation}'", color=color, attrs=["bold"])
        self._append_log("safety_hitl_decision", {"explanation": explanation, "result": result})

    def log_action_execution(self, fname: str, result: Dict[str, Any], duration_ms: float) -> None:
        """Logs the execution result of an action."""
        if "error" in result:
            termcolor.cprint(f"  ❌ Failed ({fname}): {result['error']}", color="red")
        else:
            termcolor.cprint(f"  ✅ Executed ({fname}) in {duration_ms:.1f}ms", color="green")
        self._append_log("action_execution", {"name": fname, "result": result, "duration_ms": duration_ms})

    def log_turn_summary(self, turn_index: int, interaction_id: str) -> None:
        """Logs the completion of an agent turn."""
        termcolor.cprint(f"--- Completed Turn {turn_index} (Interaction ID: {interaction_id}) ---", color="grey")
        self._append_log("turn_summary", {"turn": turn_index, "interaction_id": interaction_id})

    def log_task_complete(self, final_text: str) -> None:
        """Logs the completion of the entire task."""
        termcolor.cprint(f"\n[TASK COMPLETED]\n{final_text}", color="green", attrs=["bold"])
        self._append_log("task_complete", {"final_text": final_text})

    def log_task_failed(self, reason: str) -> None:
        """Logs a task failure or block."""
        termcolor.cprint(f"\n[TASK HALTED] {reason}", color="red", attrs=["bold"])
        self._append_log("task_failed", {"reason": reason})
