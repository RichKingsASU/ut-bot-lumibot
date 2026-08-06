import sys
import subprocess
import fnmatch

# Protected execution files are HUMAN-ONLY. Modifying via AI is blocked.
PROTECTED_PATTERNS = [
    "strategies/ut_bot.py",
    "strategies/options_executor.py",
    "signal_engine/*",
    "k2_atr_strategy.py",
    "utbot_paper_trader.py",
    "adapters/supabase_logger.py",
    "common/safe_write.py"
]

def get_staged_python_files():
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True
        )
        return [f for f in result.stdout.splitlines() if f.strip().endswith(".py")]
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}", file=sys.stderr)
        return []

def main():
    staged_files = get_staged_python_files()
    blocked = False
    
    for file in staged_files:
        for pattern in PROTECTED_PATTERNS:
            if fnmatch.fnmatch(file, pattern):
                print(f"ðŸ›‘ CRITICAL SECURITY VIOLATION: Agent attempted to modify protected file: {file}", file=sys.stderr)
                print("   FDE Safeguard: Protected execution files are HUMAN-ONLY. Modifying via AI is blocked.", file=sys.stderr)
                blocked = True
                break

    if blocked:
        sys.exit(1)
    else:
        print("âœ… COMMIT GUARD: No protected files modified. Safe to proceed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
