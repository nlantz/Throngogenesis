"""Starting game. The art director is free to replace this file."""
import json
import math
import os
import random
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'world.json'
EVENTS = ROOT / 'events.jsonl'
STOP = Path(os.environ['LIVING_GAME_STOP'])
SMOKE = os.environ.get('LIVING_GAME_SMOKE') == '1'
W, H = 800, 520


def event(kind, **data):
    with EVENTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'event': kind, **data}) + '\n')


def save():
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(world, indent=2), encoding='utf-8')
    tmp.replace(STATE)


pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption('Throngogenesis')
font = pygame.font.Font(None, 24)
clock = pygame.time.Clock()
world = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {
    'creatures': [{'x': W / 2, 'y': H / 2, 'energy': 2}], 'food': [], 'elapsed': 0
}
frames = 0
since_save = 0
running = True
while running and not STOP.exists():
    dt = min(clock.tick(30) / 1000, 0.1)
    world['elapsed'] += dt
    since_save += dt
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            x, y = e.pos
            world['food'].append([x, y])
            event('player_placed_food', x=x, y=y)
    for c in list(world['creatures']):
        if world['food']:
            target = min(world['food'], key=lambda p: math.hypot(p[0]-c['x'], p[1]-c['y']))
            dx, dy = target[0]-c['x'], target[1]-c['y']
            d = math.hypot(dx, dy)
            if d < 9:
                world['food'].remove(target)
                c['energy'] += 1
                event('creature_ate', x=round(c['x']), y=round(c['y']))
                if c['energy'] >= 4 and len(world['creatures']) < 30:
                    c['energy'] = 1
                    world['creatures'].append({'x': c['x'], 'y': c['y'], 'energy': 1})
                    event('creature_born', population=len(world['creatures']))
            elif d:
                c['x'] += 50 * dx / d * dt
                c['y'] += 50 * dy / d * dt
        else:
            c['x'] += random.uniform(-45, 45) * dt
            c['y'] += random.uniform(-45, 45) * dt
        c['x'] = max(12, min(W-12, c['x']))
        c['y'] = max(45, min(H-12, c['y']))
    screen.fill((40, 80, 59))
    for p in world['food']:
        pygame.draw.circle(screen, (245, 179, 79), p, 4)
    for c in world['creatures']:
        x, y = int(c['x']), int(c['y'])
        pygame.draw.circle(screen, (246, 230, 169), (x, y), 11)
        pygame.draw.circle(screen, (30, 45, 35), (x-3, y-2), 2)
        pygame.draw.circle(screen, (30, 45, 35), (x+3, y-2), 2)
    screen.blit(font.render('Click anywhere to leave food.', True, (240, 245, 230)), (12, 12))
    pygame.display.flip()
    if since_save >= 2:
        save()
        since_save = 0
    frames += 1
    if SMOKE and frames >= 8:
        break
save()
pygame.quit()
