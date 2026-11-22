# Throngogenesis — Petri containment prototype

A tiny creature game with an LLM art director. Inspired by Thronglets. This branch replaces native execution of the evolving game with Eryx (CPython compiled to WebAssembly, running in Wasmtime). The only host application code is the fixed supervisor and renderer.

## Run

Use 64-bit CPython 3.12 or newer and Git. No Docker or guest OS setup.

```powershell
git clone -b containment https://github.com/nlantz/Throngogenesis.git
cd Throngogenesis
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest -v test_containment
.\.venv\Scripts\python supervisor.py
```

Click to place food. Esc or window close exits. Run the containment tests before enabling evolution. If they fail, stop; there is no native fallback.

## Enable the director

```powershell
$env:LIVING_GAME_MODEL = 'YOUR_MODEL_ID'
$env:LIVING_GAME_API_KEY = 'YOUR_API_KEY'
# Optional: override the full HTTPS chat completions endpoint:
# $env:LIVING_GAME_URL = 'https://example.com/v1/chat/completions'
# Optional: set LIVING_GAME_KEY_HEADER for a raw API key header.
.\.venv\Scripts\python supervisor.py --allow-evolution
```

The supervisor sends the current game, assets, state, journal and recent gameplay
events to the configured API. The model can change any of these or do nothing.
Default: every five minutes of play, maximum 12 API calls per session.
A 120-frame smoke test with varied time steps and input is run in a fresh
sandbox before committing changes. Geometry is bounded and rounded; empty
rectangles are skipped. A runtime failure attempts to restore the previous
checkpoint, preserving the rejected generation in a local refs/petri/rejected/
ref. Saves created before this change may not yet have a rollback ref.
For a quick trial add --interval 30 --max-calls 2.
The API output cap is --max-tokens (default 8192, sent as max_completion_tokens;
the provider must support that parameter). A call/token cap is NOT a hard dollar
cap. Set a provider-side budget. No URL, headers, credentials, requests, or
external tools are controlled by the guest. HTTPS redirects are refused.

## The Petri dish

- No guest network configuration, host mounts, environment forwarding or callbacks.
- Guest memory capped at 128 MiB, virtual filesystem at 4 MiB, execution at 1 second per call.
- No native imports of the mutable game, even for testing. No native fallback.
- Host receives only JSON state, event data and bounded primitive drawing commands.
- Only four fixed text files may be replaced by the LLM: main.py, world.json,
  assets.json and journal.md. Sprites are procedural or JSON pixel/vector art.
- The initial interface supports mouse events and keyboard input; the fixed host
  renderer provides circles, rectangles, lines, polygons and text.
- The separate world-contained/ Git repository on branch evolution is the save.
  No remote is configured. Existing world/ saves from main are left untouched.

The sandbox is not an operating system security guarantee. Eryx/Wasmtime,
the Python binding, JSON handling and the renderer are trusted dependencies;
sandbox vulnerabilities remain possible. Guest stdout is checked for size
after Eryx returns it, not during capture; host memory/CPU/disk are not subject
to independent OS quotas. Git history grows over time. This is an experimental
containment layer, not security-certified software. For adversarial testing or
sensitive hosts use additional OS/VM isolation. No API or Windows runtime test
has been performed by the author of this branch; run the included tests locally.
An accepted game may still fail later. Automatic rollback is best effort;
if it cannot restore the previous checkpoint, stop and use Git history.

```powershell
git -C world-contained log --oneline
```

To restore an older commit, stop the game, make a backup branch if desired,
then run git -C world-contained reset --hard COMMIT. Do not change branches
while the supervisor is running.
