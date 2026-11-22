"""Mutable creature game. Only executed inside Petri."""
import math
import random


def step(state, inputs, dt, assets):
    if state is None:
        state = {'creatures': [{'x': 400, 'y': 260, 'energy': 2}],
                 'food': [], 'elapsed': 0}
    state['elapsed'] += dt
    events = []
    for e in inputs:
        if e['type'] == 'click' and e['button'] == 1 and len(state['food']) < 150:
            state['food'].append(e['pos'])
    for c in list(state['creatures']):
        if state['food']:
            target = min(state['food'], key=lambda p: math.hypot(p[0]-c['x'], p[1]-c['y']))
            dx, dy = target[0]-c['x'], target[1]-c['y']
            d = math.hypot(dx, dy)
            if d < 9:
                state['food'].remove(target)
                c['energy'] += 1
                events.append({'event': 'ate', 'x': round(c['x']), 'y': round(c['y'])})
                if c['energy'] >= 4 and len(state['creatures']) < 30:
                    c['energy'] = 1
                    state['creatures'].append({'x': c['x'], 'y': c['y'], 'energy': 1})
                    events.append({'event': 'born', 'population': len(state['creatures'])})
            elif d:
                c['x'] += 50 * dx / d * dt
                c['y'] += 50 * dy / d * dt
        else:
            c['x'] += random.uniform(-60, 60) * dt
            c['y'] += random.uniform(-60, 60) * dt
        c['x'] = max(12, min(788, c['x']))
        c['y'] = max(45, min(508, c['y']))
    draw = [['fill', assets.get('field', [40, 80, 59])]]
    for p in state['food']:
        draw.append(['circle', [245, 179, 79], p, 4])
    for c in state['creatures']:
        x, y = int(c['x']), int(c['y'])
        draw.extend([['circle', assets.get('creature', [246, 230, 169]), [x, y], 11],
                     ['circle', [30, 45, 35], [x-3, y-2], 2],
                     ['circle', [30, 45, 35], [x+3, y-2], 2]])
    draw.append(['text', [240, 245, 230], [12, 12], 'Click anywhere to leave food.'])
    return {'state': state, 'draw': draw, 'events': events[:32]}
