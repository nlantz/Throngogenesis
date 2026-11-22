"""Trusted boundary: guest Python runs exclusively in Eryx, never CPython."""
import json
import math
import eryx

W, H = 800, 520
MAX_FRAME = 262144
MAX_STATE = 65536
MAX_ASSETS = 65536
MAX_SOURCE = 65536
MAX_EVENTS = 32


def encode(obj):
    return json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def bounded(obj, limit):
    text = encode(obj)
    if len(text) > limit:
        raise ValueError('JSON exceeds size limit')
    return text


def integer(v, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError('Invalid integer in drawing command')
    return v


def color(v):
    if not isinstance(v, list) or len(v) != 3:
        raise ValueError('Expected RGB color')
    return [integer(c, 0, 255) for c in v]


def geometry(v, lo, hi):
    # Quantize only finite, bounded numbers; bool is not a coordinate.
    if type(v) not in (int, float) or not lo <= v <= hi:
        raise ValueError('Drawing geometry outside permitted bounds')
    return round(v)


def point(v):
    if not isinstance(v, list) or len(v) != 2:
        raise ValueError('Expected point')
    return [geometry(c, -4096, 4096) for c in v]


def validate_commands(commands):
    if not isinstance(commands, list) or len(commands) > 1024:
        raise ValueError('Too many drawing commands')
    normalized = []
    for command in commands:
        if not isinstance(command, list) or not command:
            raise ValueError('Malformed drawing command')
        op, *a = command
        if op == 'fill' and len(a) == 1:
            color(a[0])
        elif op == 'circle' and len(a) == 3:
            a = [color(a[0]), point(a[1]), geometry(a[2], 0, 1024)]
            if a[2] == 0:
                continue
        elif op == 'rect' and len(a) == 3:
            rgb, pos = color(a[0]), point(a[1])
            if not isinstance(a[2], list) or len(a[2]) != 2:
                raise ValueError('Expected rectangle size')
            size = [geometry(n, -2048, 2048) for n in a[2]]
            if min(size) <= 0:
                continue
            a = [rgb, pos, size]
        elif op == 'line' and len(a) == 4:
            a = [color(a[0]), point(a[1]), point(a[2]), geometry(a[3], 1, 32)]
        elif op == 'polygon' and len(a) == 2:
            color(a[0])
            if not isinstance(a[1], list) or not 3 <= len(a[1]) <= 128:
                raise ValueError('Invalid polygon')
            a = [color(a[0]), [point(p) for p in a[1]]]
        elif op == 'text' and len(a) == 3:
            color(a[0]); point(a[1])
            if not isinstance(a[2], str) or len(a[2]) > 160 or '\x00' in a[2]:
                raise ValueError('Invalid text')
            a[2].encode('utf-8')
            a = [color(a[0]), point(a[1]), a[2]]
        else:
            raise ValueError('Unknown drawing command')
        normalized.append([op, *a])
    return normalized


def validate_frame(frame):
    if not isinstance(frame, dict) or set(frame) != {'state', 'draw', 'events'}:
        raise ValueError('Expected state, draw and events')
    bounded(frame['state'], MAX_STATE)
    frame['draw'] = validate_commands(frame['draw'])
    events = frame['events']
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError('Too many guest events')
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Expected event object')
        bounded(event, 512)
    return frame


def new_session(timeout=1000):
    # No network, volumes, VFS mounts, environment forwarding or callbacks.
    # Never replace this with exec(), eval(), pickle or a native game launch.
    return eryx.Session(resource_limits=eryx.ResourceLimits(
        execution_timeout_ms=timeout,
        max_memory_bytes=128 * 1024 * 1024,
        max_vfs_bytes=4 * 1024 * 1024,
        max_callback_invocations=0,
    ))


class Petri:
    def __init__(self, source, assets):
        if len(source.encode('utf-8')) > MAX_SOURCE:
            raise ValueError('Game source too large')
        self.assets = bounded(assets, MAX_ASSETS)
        self.session = new_session()
        result = self.session.execute(source)
        if result.stdout.strip():
            raise ValueError('Guest initialization must not print')

    def step(self, state, inputs, dt):
        # repr of a JSON string is a Python string literal, not executable data.
        payload = bounded({'state': state, 'inputs': inputs, 'dt': dt}, MAX_FRAME)
        script = ("import json as _petri_json\n"
                  "_petri_in = _petri_json.loads(" + repr(payload) + ")\n"
                  "_petri_assets = _petri_json.loads(" + repr(self.assets) + ")\n"
                  "print(_petri_json.dumps(step(_petri_in['state'], "
                  "_petri_in['inputs'], _petri_in['dt'], _petri_assets), "
                  "allow_nan=False))")
        output = self.session.execute(script).stdout
        if len(output) > MAX_FRAME:
            raise ValueError('Guest output too large')
        return validate_frame(json.loads(output))


def render(pygame, screen, font, commands):
    # Only bounded primitive drawing; no guest paths, fonts, native image
    # decoders, clipboard, web links, subprocesses, or arbitrary host calls.
    screen.fill((0, 0, 0))
    for op, *a in commands:
        if op == 'fill':
            screen.fill(a[0])
        elif op == 'circle':
            pygame.draw.circle(screen, a[0], a[1], a[2])
        elif op == 'rect':
            pygame.draw.rect(screen, a[0], (*a[1], *a[2]))
        elif op == 'line':
            pygame.draw.line(screen, a[0], a[1], a[2], a[3])
        elif op == 'polygon':
            pygame.draw.polygon(screen, a[0], a[1])
        elif op == 'text':
            screen.blit(font.render(a[2], True, a[0]), a[1])
