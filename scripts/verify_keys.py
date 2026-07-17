#!/usr/bin/env python3
"""
Verify the three scoped Anthropic API keys.
"""

import os
import sys
import anthropic

def main():
    keys = {
        "ANTHROPIC_API_KEY_AGENTS": os.getenv("ANTHROPIC_API_KEY_AGENTS", ""),
        "ANTHROPIC_API_KEY_SENTIMENT": os.getenv("ANTHROPIC_API_KEY_SENTIMENT", ""),
        "ANTHROPIC_API_KEY_HERMES": os.getenv("ANTHROPIC_API_KEY_HERMES", ""),
    }
    
    any_failed = False
    
    for key_name, key_val in keys.items():
        key_val = key_val.strip()
        if not key_val:
            print(f"FAIL: {key_name} is not set in the environment.")
            any_failed = True
            continue
            
        try:
            client = anthropic.Anthropic(api_key=key_val, timeout=10.0)
            # Ping each with claude-haiku-4-5-20251001, max_tokens=10
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[
                    {"role": "user", "content": "Ping"}
                ]
            )
            print(f"PASS: {key_name}")
        except Exception as e:
            print(f"FAIL: {key_name} - {str(e)}")
            any_failed = True
            
    if any_failed:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
