# Claude Code connection and first workflow

Use the MCP URL and **personal Scientific AI API key** in your organizer's
private handoff. Your LibreChat password and Claude credits are not that key.

Install the checksummed Scientific AI skill bundle using its existing installer:

```bash
python3 bundle.py verify
python3 bundle.py install --dest "$HOME/.claude/skills"
```

Run these commands from the extracted `scientific-ai` bundle. Identical skills
are a no-op; the installer stops on conflicting installed files. Preserve any
customized skill rather than overwriting it.

Merge this entry into your project's `.mcp.json`, preserving existing servers:

```json
{
  "mcpServers": {
    "scientific-ai": {
      "type": "http",
      "url": "${SCIENTIFIC_MODELS_MCP_URL}",
      "headers": {
        "Authorization": "Bearer ${SCIENTIFIC_MODELS_API_KEY}"
      }
    }
  }
}
```

Set the URL from your handoff and enter the key without putting it into shell
history. This example is for Bash:

```bash
export SCIENTIFIC_MODELS_MCP_URL='https://YOUR-ISSUED-HOST/mcp'
read -rsp 'Personal Scientific AI API key: ' SCIENTIFIC_MODELS_API_KEY
printf '\n'
export SCIENTIFIC_MODELS_API_KEY
claude
```

Within Claude Code, inspect `/mcp` and approve the project connection if prompted.
Start `/scientific-ai-hackathon` and request:

> List the Scientific AI models available to my account and inspect the schema
> for one relevant model. Do not submit a job yet. Explain the required inputs,
> output files and a small first experiment.

This verifies authentication and discovery without scientific compute. A model
schema is a connectivity check, not an inference result. If authentication
fails, verify your issued URL/key and the current process environment. Never
print the key into chat, commit it or replace it with a shared service key.

## Five-minute walkthrough

1. **Open the workbench:** sign in using your separate workbench URL/login.
   Open Workspace and browse the supplied `examples/` directory.
2. **Choose inputs:** describe the objective and identify the exact existing
   example or uploaded sequence/structure. Ask the agent to read its format.
3. **Review a small plan:** choose a catalog model and its actual parameters.
   For MD, use the precheck when appropriate and inspect its findings before a
   production simulation. Do not mistake a precheck report for dynamics.
4. **Run once:** authorize the small experiment. Save the returned operation ID;
   queued/running work remains the same job if the chat disconnects.
5. **Inspect the result:** open the report/structure, download the raw artifacts
   and retain the parameters. Compare model predictions with their stated
   scientific meaning before scaling the experiment.

Claude Code uses the same hosted model MCP, but does not inherit LibreChat's
workspace mount, viewers or background study executor. Use the bundle's
[portable client contract](../../scientific-gateway/references/portable-client.md)
for trusted artifact transfer. Do not claim those extra tools are installed by
adding an MCP URL. Keep requests within the organizer's assigned capacity.
The portable client uses these same two environment variables. Its worked
RFdiffusion example creates and verifies source/manifest artifacts, submits once,
polls and downloads actual outputs without a LibreChat installation.

Official client references: [MCP configuration and environment expansion](https://code.claude.com/docs/en/mcp),
[skill installation](https://code.claude.com/docs/en/skills).
