# Throngogenesis

A tiny creature game with an LLM as art director. Inspired by Thronglets. The game can change into anything.

## Start (Windows PowerShell)

Install Python 3.10+ and Git, then open a terminal in this directory.

```powershell
python -m pip install -r requirements.txt
python supervisor.py
```

Click to place food. Creatures eat and reproduce. Closing the game saves it.

## Enable evolution

**Generated Python executes with your OS user's privileges. This MVP is not a security sandbox.** Use a disposable VM with no personal files, mounted host folders or sensitive credentials. The supervisor is outside the evolving Git repository and excluded from the edit interface, but generated code could still modify it. A smoke test runs generated code too.

Configure an OpenAI-compatible chat completions API, with a coding-capable model supported by your provider:

```powershell
$env:LIVING_GAME_MODEL = 'YOUR_MODEL_ID'
$env:LIVING_GAME_API_KEY = 'YOUR_API_KEY'
# Optional: for a different compatible provider, set its full endpoint URL.
# $env:LIVING_GAME_URL = 'https://example.com/v1/chat/completions'
python supervisor.py --allow-evolution
```

For providers expecting a raw API key in a custom header rather than Bearer authentication, set `LIVING_GAME_KEY_HEADER` to the header name. On Linux/macOS use `export` instead of PowerShell environment variables.

The game pauses every five minutes of play for the art director to review its source, saved world, recent events, journal and recent commit messages. The director may rewrite the game, add assets, delete files or do nothing. Changes are checked for Python syntax and tested by starting the game in a temporary headless copy. A failed candidate is rolled back. The game then restarts. NPC activity is treated the same as player activity for the MVP; no coefficients.

The default session limit is 12 API calls; afterward the game keeps running without further calls. This is a call cap, **not a dollar cap**. Check your provider's spending limits. For a quick trial:

```powershell
python supervisor.py --allow-evolution --interval 30 --max-calls 2
```

The interval is measured while the game runs; API and test time are additional. Closing during ordinary gameplay or pressing Ctrl+C ends the session.

## The save is Git

On first launch, `seed/` is copied into `world/`, a separate local Git repository on branch `evolution`. All durable game code, assets, state and creative journal live there. The original seed and supervisor remain outside it. No remote is configured or needed.

```powershell
git -C world log --oneline
git -C world show HEAD
```

To restore a previous version, stop the supervisor and use `git -C world reset --hard <commit>` (this discards later changes from the branch; create a backup branch first if desired). Do not switch branches while the supervisor is running.

## Scope

One Python supervisor, one seed game, one external dependency (pygame), one provider-independent OpenAI-compatible HTTP interface. No scheduler, external database, web server or additional agent framework. The supervisor provides a simple fixed launch and stop protocol, not a comprehensive game-testing framework. Generated games need to preserve that protocol but can otherwise change their mechanics and art freely.
