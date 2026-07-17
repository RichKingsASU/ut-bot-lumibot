# Anti-gravity Memory (Claude-Mem Equivalent)

1. Maintain continuous causality tracking across all sessions.
2. Ensure decisions made in past phases of the project are retained and enforced.
3. Consult `Temp/findings.md` and `Temp/task_plan.md` for historical debugging context.
4. If a port mismatch or missing dependency occurs, the Self-Annealing Protocol mandates that the agent must self-diagnose, apply a fix, update the execution scripts, and retry automatically without prompting the user.

# Agent Personas

## Reviewer Sub-Agent
Audits code with fresh context, ensuring all commits align with the DO Architecture and BLAST framework requirements.

## Documenter Sub-Agent
Continuously updates `Directive` specifications to remain aligned with the raw execution scripts in `Execution`.
