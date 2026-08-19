"""Agent loop for Gemini Computer Use API using Interactions API."""

import base64
import json
import time
from typing import Any, Dict, List, Optional
from google import genai
from agent_config import AgentConfig
from logging_utils import AuditLogger
from safety import SafetyManager, SYSTEM_SAFETY_INSTRUCTION
from browser_env import BrowserEnvironment


class ComputerUseAgent:
    """Orchestrates the Gemini Computer Use agent loop."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = AuditLogger(log_dir=config.log_dir, screenshots_dir=config.screenshots_dir)
        self.safety_manager = SafetyManager(logger=self.logger)
        self.browser_env = BrowserEnvironment(config=self.config)
        self.client = genai.Client()

    def run(self, task_prompt: str) -> Optional[str]:
        """Runs the computer use agent loop for a user-specified task prompt."""
        self.logger.log_user_prompt(prompt=task_prompt, initial_url=self.config.initial_url or "about:blank")

        # Start browser environment
        self.browser_env.start()

        try:
            # Capture initial screenshot
            initial_screenshot = self.browser_env.capture_screenshot()
            self.logger.save_screenshot(initial_screenshot, turn_index=0)
            initial_b64 = base64.b64encode(initial_screenshot).decode("utf-8")

            tools = [
                {
                    "type": "computer_use",
                    "environment": "browser",
                    "enable_prompt_injection_detection": self.config.enable_prompt_injection_detection,
                }
            ]

            # First turn: Send task prompt + initial screenshot
            print(f"Sending initial task to Gemini model '{self.config.model}'...")
            interaction = self.client.interactions.create(
                model=self.config.model,
                input=[
                    {"type": "text", "text": task_prompt},
                    {"type": "image", "data": initial_b64, "mime_type": "image/png"},
                ],
                tools=tools,
                system_instruction=SYSTEM_SAFETY_INSTRUCTION,
            )

            # Turn Loop
            for turn in range(1, self.config.max_turns + 1):
                self.logger.log_turn_summary(turn, interaction.id)

                # Process steps from interaction response
                model_thoughts = []
                function_calls = []

                for step in interaction.steps:
                    if step.type == "model_output":
                        for block in getattr(step, "content", []):
                            if getattr(block, "type", None) == "text" or hasattr(block, "text"):
                                model_thoughts.append(getattr(block, "text", ""))
                    elif step.type == "function_call":
                        function_calls.append(step)

                if model_thoughts:
                    thought_text = " ".join(model_thoughts)
                    self.logger.log_model_thought(thought_text)

                # If no function calls returned, the agent completed the task
                if not function_calls:
                    final_response = " ".join(model_thoughts) if model_thoughts else "Task completed."
                    self.logger.log_task_complete(final_response)
                    return final_response

                # Execute suggested function calls
                results = []
                for fcall in function_calls:
                    fname = fcall.name
                    fargs = dict(fcall.arguments) if hasattr(fcall, "arguments") and fcall.arguments else {}

                    # Extract safety decision if present
                    safety_decision = fargs.pop("safety_decision", None)
                    if safety_decision is None and hasattr(fcall, "safety_decision"):
                        safety_decision = getattr(fcall, "safety_decision")

                    self.logger.log_suggested_action(fname, fargs, safety_decision)

                    safety_acknowledgement = False
                    if safety_decision:
                        status, acknowledged = self.safety_manager.process_safety_decision(safety_decision)
                        if status == "HALT":
                            self.logger.log_task_failed(f"Halted due to safety decision or user denial on '{fname}'")
                            return "Task halted by safety policy or user."
                        safety_acknowledgement = acknowledged

                    # Execute action
                    start_time = time.time()
                    exec_result = self.browser_env.execute_action(fname, fargs)
                    duration_ms = (time.time() - start_time) * 1000.0

                    if safety_acknowledgement:
                        exec_result["safety_acknowledgement"] = True

                    self.logger.log_action_execution(fname, exec_result, duration_ms)
                    results.append((fname, fcall.id, exec_result))

                # Capture state (screenshot + URL) after actions
                current_screenshot = self.browser_env.capture_screenshot()
                self.logger.save_screenshot(current_screenshot, turn_index=turn)
                screenshot_b64 = base64.b64encode(current_screenshot).decode("utf-8")
                current_url = self.browser_env.get_current_url()

                # Build function_result steps for the next API call
                function_responses = []
                for fname, call_id, res_data in results:
                    function_responses.append({
                        "type": "function_result",
                        "name": fname,
                        "call_id": call_id,
                        "result": [
                            {
                                "type": "text",
                                "text": json.dumps({"url": current_url, **res_data}),
                            },
                            {
                                "type": "image",
                                "data": screenshot_b64,
                                "mime_type": "image/png",
                            },
                        ],
                    })

                # Create next interaction turn
                interaction = self.client.interactions.create(
                    model=self.config.model,
                    previous_interaction_id=interaction.id,
                    input=function_responses,
                    tools=tools,
                    system_instruction=SYSTEM_SAFETY_INSTRUCTION,
                )

            self.logger.log_task_failed(f"Reached maximum turn limit ({self.config.max_turns}) without completion.")
            return f"Agent hit max turn limit ({self.config.max_turns})."

        finally:
            self.browser_env.stop()
