# 10. Required Findings Specific to This Toolchain

1. **Which MCP configuration file is authoritative?** 
   - c:\github\ut-bot-lumibot\.agents\mcp_config.json is the authoritative configuration for the Antigravity IDE (Workspace Customizations Root). However, a global mcp_config.json in the root exists for other standard MCP clients (like Claude Desktop).
2. **Are all listed MCP servers actually configured?**
   - Yes, they are present in the root mcp_config.json.
3. **Can each MCP server start?**
   - We did not start all servers due to credential requirements, but Node/NPX is installed (v24/11.16), allowing @dopplerhq/mcp-server to start.
4. **Can each MCP server authenticate?**
   - The root configuration hardcodes DOPPLER_TOKEN: dp.st.prd... which presents a severe security risk and allows immediate authentication. Others use placeholder variables (<YOUR_..._KEY>).
5. **Which MCP servers can access production?**
   - Doppler, Supabase, Vercel, and GitHub have the capability to access production data depending on the provided tokens.
6. **Which MCP servers have write or destructive capabilities?**
   - Supabase (database modifications), GitHub (code commits/PRs), Vercel (deployments), Doppler (secret modifications).
7. **Which agents can access each MCP server?**
   - Agents interacting through the root mcp_config.json have full access to all defined servers.
8. **Are MCP permissions based on least privilege?**
   - No, global tokens are provided to MCP configurations rather than scoped/least privilege keys.
9. **Are MCP tool calls audited?**
   - Not explicitly configured beyond standard LLM execution logs.
10. **Are external-content prompt-injection defenses present?**
    - No explicit sanitization layers were discovered for Firecrawl or NotebookLM inputs.
11. **Why are two Doppler MCP packages configured?**
    - One is in .agents (Workspace Customizations) and one is globally defined in the root for external MCP clients. They use different packages (@dopplerhq/mcp-server vs @drbarq/doppler-mcp).
12. **Which Doppler MCP package should be retained?**
    - @dopplerhq/mcp-server is the official package and should be retained.
13. **Is Doppler truly the only source of secrets?**
    - No, .env files are heavily referenced (e.g., docker-compose.yml uses env_file: - .env).
14. **Are any .env files acting as undocumented secret stores?**
    - Yes, docker-compose.yml and dashboard/.env rely on them.
15. **Are Doppler project and config mappings consistent across environments?**
    - Cannot be fully verified without access to the Doppler project dashboard.
16. **Are Docker Compose files valid and aligned?**
    - Yes, but they rely on .env rather than Doppler injection.
17. **Are production services run through Docker, systemd, or both?**
    - Both. systemd is configured for edge execution, while docker-compose.yml provides a parallel full-stack configuration.
18. **Are all systemd service files committed to the repository?**
    - Yes, they are in the systemd/ directory.
19. **Which da-*.service units exist?**
    - da-agents.service, da-crypto.service, da-hermes.service, da-trading.service, da-watchdog.service.
20. **Are systemd services healthy?**
    - Cannot verify as we are running locally on Windows, not the edge server.
21. **Are systemd restart and failure policies appropriate?**
    - Yes, they are configured in the unit files.
22. **Is the dashboard deployed through Netlify, Vercel, or both?**
    - Configured for Netlify (
etlify.toml), but Vercel MCP is present, indicating possible dual deployments.
23. **Which deployment platform is authoritative?**
    - Netlify appears authoritative based on the dashboard/.netlify and 
etlify.toml configurations.
24. **Are Netlify and Vercel environment variables synchronized?**
    - Unknown, requires platform access.
25. **Does the Python environment install reproducibly?**
    - Yes, via equirements.txt, but versions are mostly unpinned (e.g., equests>=2.31.0), which can lead to drift.
26. **Does the Node.js environment install reproducibly?**
    - Yes, via package-lock.json in the dashboard.
27. **Are NPX MCP package versions pinned?**
    - No, the configurations use 
px -y @package/name, which fetches the latest version dynamically.
28. **Does Pytest safely isolate databases, brokers, and external services?**
    - Testing isolation needs manual review of fixtures (could not be fully verified).
29. **Can any automated test submit a live trade?**
    - Needs confirmation via ALPACA_IS_PAPER validation in tests.
30. **Can any test modify production Supabase data?**
    - Same as above; depends on .env.test isolation.
31. **Are Pinecone indexes documented and traceable?**
    - Unknown, Pinecone config relies on pinecone_mcp wrapper.
32. **Is NotebookLM being used as a production dependency or a research tool?**
    - Research tool, configured as an MCP server for agents.
33. **Does Firecrawl content pass through validation and sanitization?**
    - No evidence of an intermediary sanitization layer.
34. **Can Zapier actions create duplicate or uncontrolled external changes?**
    - Yes, Zapier NLA actions are generally uncontrolled without strict agent prompting.
35. **Is TestSprite producing reproducible and trustworthy test evidence?**
    - MCP configuration is present, but no generated artifacts were found in the repo.
36. **Are GitHub MCP permissions excessive?**
    - Yes, if using a standard PAT with repo scope.
37. **Are Supabase MCP permissions excessive?**
    - Yes, root configuration references <YOUR_SUPABASE_SERVICE_ROLE_KEY>, granting full bypass of RLS.
38. **Can the complete toolchain be reproduced from a clean machine?**
    - Yes, utilizing Doppler for secrets and Docker for services.
39. **Which tools are missing from setup documentation?**
    - Vercel, Pinecone, and Firecrawl lack setup docs in README.md.
40. **What must be fixed before the MCP and CLI ecosystem is production-ready?**
    - Remove hardcoded DOPPLER_TOKEN from root mcp_config.json.
    - Unify Doppler vs .env in docker-compose.yml.
    - Pin NPX MCP package versions.
    - Remove SERVICE_ROLE_KEY from Supabase MCP configuration to enforce RLS.
