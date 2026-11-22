"""Fixed supervisor; only the separate world repository is editable by the director."""
import argparse
import ast
import base64
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
WORLD = ROOT / 'world'
STOP = ROOT / '.stop-game'
BRANCH = 'evolution'
DIRECTOR = '''You are the art director of a living, evolving digital experience.
You have creative control over its source code, artwork, mechanics, narrative,
interface and world. Consider what has happened in the game, including what
players explore, seek out, experiment with, ignore or repeatedly interact with,
and what the world and its inhabitants have done. Develop these interests where
appropriate, but use your own creative judgment. You may introduce, modify or
abandon any concept, including the original premise. Maintain continuity where
you find it meaningful. You may also decide no change is warranted. There is no
predetermined completion state.

Return only a JSON object: {"summary":"short commit message", "files": {"relative/path.py":"complete file contents"}, "delete": ["relative/path"], "binary": {"relative/path.png":"base64"}}.
All keys other than summary are optional. For no change return {"summary":"No change"}.
Update journal.md if useful. Generate assets directly or procedurally.
The fixed supervisor starts main.py using Python; it must run until window close
or the stop file specified by LIVING_GAME_STOP appears. When LIVING_GAME_SMOKE=1,
main.py must initialize and exit successfully within 12 seconds. Persist game
state as appropriate and append meaningful gameplay events as JSON lines to
 events.jsonl. Do not modify the supervisor, Git metadata or external files;
do not use network, external commands, credentials or install dependencies.
Python standard library and pygame are available. File writes replace entire files.'''


def git(*args):
    return subprocess.check_output(['git', '-C', str(WORLD), *args], text=True, stderr=subprocess.STDOUT).strip()


def commit(message):
    git('add', '-A')
    if git('status', '--porcelain'):
        git('-c', 'user.name=Throngogenesis', '-c', 'user.email=living-game@localhost',
            'commit', '-m', message[:180] or 'Evolution')


def setup():
    if not WORLD.exists():
        shutil.copytree(ROOT / 'seed', WORLD)
    if not (WORLD / '.git').exists():
        if any((WORLD / p).exists() for p in ['.git']):
            raise RuntimeError('Expected an independent local repository')
        git('init', '-b', BRANCH)
        commit('Seed world')
    if git('branch', '--show-current') != BRANCH:
        raise RuntimeError(f'Expected the {BRANCH} branch; refusing to modify another branch.')
    if Path(git('rev-parse', '--show-toplevel')).resolve() != WORLD.resolve():
        raise RuntimeError('World must have its own Git repository.')


def game_env(stop, smoke=False):
    env = dict(os.environ)
    # Avoid handing the model-generated program the API credentials directly.
    for key in list(env):
        if any(word in key.upper() for word in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
            env.pop(key)
    env['LIVING_GAME_STOP'] = str(stop)
    env['LIVING_GAME_SMOKE'] = '1' if smoke else '0'
    if smoke:
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    return env


def launch(directory, stop, smoke=False):
    return subprocess.Popen([sys.executable, 'main.py'], cwd=directory, env=game_env(stop, smoke))


def stop_game(proc):
    STOP.touch()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    finally:
        STOP.unlink(missing_ok=True)


def context():
    files = {}
    for name in git('ls-files').splitlines():
        p = WORLD / name
        if name == 'events.jsonl' or not p.is_file() or p.is_symlink():
            continue
        if p.stat().st_size > 100_000:
            files[name] = '[large file omitted]'
            continue
        try:
            files[name] = p.read_text(encoding='utf-8')
        except UnicodeError:
            files[name] = '[binary asset]'
    event_file = WORLD / 'events.jsonl'
    events = event_file.read_text(encoding='utf-8') if event_file.exists() else ''
    return {'files': files, 'recent_events': events[-24000:], 'history': git('log', '-12', '--oneline')}


def request_change():
    url = os.environ.get('LIVING_GAME_URL', 'https://api.openai.com/v1/chat/completions')
    model = os.environ['LIVING_GAME_MODEL']
    key = os.environ.get('LIVING_GAME_API_KEY', '')
    header = os.environ.get('LIVING_GAME_KEY_HEADER', 'Authorization')
    value = f'Bearer {key}' if header.lower() == 'authorization' else key
    headers = {'Content-Type': 'application/json'}
    if key:
        headers[header] = value
    body = {'model': model, 'messages': [{'role': 'system', 'content': DIRECTOR},
             {'role': 'user', 'content': json.dumps(context(), ensure_ascii=False)}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    raw = result['choices'][0]['message']['content'].strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(raw)


def safe_path(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Invalid path')
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or '..' in rel.parts or any(x.lower() == '.git' for x in rel.parts):
        raise ValueError(f'Unsafe path: {name}')
    path = WORLD.joinpath(*rel.parts)
    if path.resolve() == WORLD or not path.resolve().is_relative_to(WORLD.resolve()):
        raise ValueError(f'Unsafe path: {name}')
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != WORLD.parent):
        raise ValueError(f'Symlink path: {name}')
    return path


def apply(change):
    if not isinstance(change, dict) or not isinstance(change.get('summary'), str):
        raise ValueError('Expected JSON object with summary')
    for name in change.get('delete', []):
        safe_path(name).unlink(missing_ok=True)
    for name, contents in change.get('files', {}).items():
        path = safe_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')
    for name, contents in change.get('binary', {}).items():
        path = safe_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(contents, validate=True))


def validate():
    for p in WORLD.rglob('*.py'):
        if '.git' not in p.relative_to(WORLD).parts:
            ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    with tempfile.TemporaryDirectory() as temp:
        test = Path(temp) / 'world'
        shutil.copytree(WORLD, test, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        proc = launch(test, Path(temp) / 'stop', smoke=True)
        try:
            if proc.wait(timeout=12) != 0:
                raise RuntimeError('Game failed smoke test')
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise RuntimeError('Game smoke test timed out')


def evolve():
    # Save normal gameplay first, so rollback cannot erase it.
    commit('Gameplay checkpoint')
    checkpoint = git('rev-parse', 'HEAD')
    try:
        change = request_change()
        apply(change)
        if git('status', '--porcelain'):
            validate()
            commit(change['summary'])
        print('Director:', change['summary'], flush=True)
    except Exception as exc:
        git('reset', '--hard', checkpoint)
        git('clean', '-fd')
        print(f'Evolution skipped / rolled back: {exc}', flush=True)
    # Clear the consumed event window only after a successful request.
    else:
        (WORLD / 'events.jsonl').unlink(missing_ok=True)
        commit('Close event window')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=float, default=300, help='Seconds of play between director calls')
    parser.add_argument('--max-calls', type=int, default=12, help='Maximum API requests per session')
    parser.add_argument('--allow-evolution', action='store_true', help='Allow automatic execution of generated code; NOT sandboxed')
    args = parser.parse_args()
    if args.interval <= 0 or args.max_calls < 0:
        parser.error('Interval must be positive; max-calls cannot be negative')
    if args.allow_evolution and not os.environ.get('LIVING_GAME_MODEL'):
        parser.error('Set LIVING_GAME_MODEL before enabling evolution')
    setup()
    STOP.unlink(missing_ok=True)
    calls = 0
    proc = None
    try:
        while True:
            proc = launch(WORLD, STOP)
            deadline = time.monotonic() + args.interval
            while proc.poll() is None:
                if args.allow_evolution and calls < args.max_calls and time.monotonic() >= deadline:
                    break
                time.sleep(0.2)
            if proc.poll() is not None:
                if proc.returncode:
                    print(f'Game exited with code {proc.returncode}', flush=True)
                break
            stop_game(proc)
            calls += 1
            print(f'Evolution {calls}/{args.max_calls}', flush=True)
            evolve()
    except KeyboardInterrupt:
        pass
    finally:
        if proc is not None and proc.poll() is None:
            stop_game(proc)
        commit('Session checkpoint')


if __name__ == '__main__':
    main()
