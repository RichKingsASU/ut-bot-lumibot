"""CLI entrypoint for Gemini Computer Use Agent."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AgentConfig
from agent_loop import ComputerUseAgent



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gemini Computer Use Agent — Autonomous Browser Automation via Interactions API"
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Navigate to google.com and search for Gemini Computer Use API",
        help="Natural language instruction/task for the browser agent.",
    )
    parser.add_argument(
        "--initial-url",
        default="https://www.google.com",
        help="Initial URL to load before agent starts. Default: https://www.google.com",
    )
    parser.add_argument(
        "--model",
        default="gemini-3.6-flash",
        help="Gemini model ID to use (e.g. gemini-3.6-flash, gemini-3-flash-preview). Default: gemini-3.6-flash",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="Maximum agent interaction loop turns. Default: 10",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Launch Playwright browser with visible GUI window (non-headless).",
    )
    parser.add_argument(
        "--allowlist",
        default="",
        help="Comma-separated list of allowed domain names (e.g. google.com,wikipedia.org).",
    )
    parser.add_argument(
        "--blocklist",
        default="",
        help="Comma-separated list of prohibited domain names.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory to store audit log file and screenshot captures. Default: logs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print(
            "⚠️  Warning: GEMINI_API_KEY environment variable is not set. Ensure GEMINI_API_KEY is exported before running."
        )

    allowed_domains = [d.strip() for d in args.allowlist.split(",") if d.strip()]
    blocked_domains = [d.strip() for d in args.blocklist.split(",") if d.strip()]

    config = AgentConfig(
        model=args.model,
        max_turns=args.max_turns,
        headless=not args.headful,
        allowed_domains=allowed_domains,
        blocked_domains=blocked_domains,
        initial_url=args.initial_url,
        log_dir=args.log_dir,
        screenshots_dir=os.path.join(args.log_dir, "screenshots"),
    )

    print("==================================================")
    print("      GEMINI COMPUTER USE BROWSER AGENT")
    print("==================================================")
    print(f"Model: {config.model}")
    print(f"Viewport: {config.screen_width}x{config.screen_height}")
    print(f"Headless Mode: {config.headless}")
    print(f"Max Turns: {config.max_turns}")
    if allowed_domains:
        print(f"Domain Allowlist: {allowed_domains}")
    if blocked_domains:
        print(f"Domain Blocklist: {blocked_domains}")
    print("==================================================\n")

    agent = ComputerUseAgent(config=config)
    result = agent.run(task_prompt=args.task)

    print("\n==================================================")
    print("Execution Finished.")
    print(f"Final Result: {result}")
    print(f"Audit log saved to: {os.path.join(config.log_dir, 'audit.jsonl')}")
    print("==================================================")


if __name__ == "__main__":
    main()
