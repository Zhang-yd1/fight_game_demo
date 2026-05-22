"""输入系统测试"""

import pygame
pygame.init()
pygame.display.set_mode((800, 600), pygame.HIDDEN)

from config import FPS, PLAYER1_KEY_CONFIG, PLAYER2_KEY_CONFIG
from input_system import (
    Action, KeyConfig, InputBuffer, InputManager,
)
from states import (
    GameContext, StateID,
    MenuState, FightState, PauseState, ResultState,
    make_fighters, check_attack,
)

screen = pygame.display.get_surface()
clock = pygame.time.Clock()
fonts = {
    'hud':    pygame.font.SysFont('SimHei', 18, bold=True),
    'result': pygame.font.SysFont('SimHei', 56, bold=True),
    'hint':   pygame.font.SysFont('SimHei', 22),
    'guide':  pygame.font.SysFont('SimHei', 14),
}

ctx = GameContext(screen, clock, fonts)
ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG)
ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)

states = {
    StateID.MENU:   MenuState(),
    StateID.FIGHT:  FightState(),
    StateID.PAUSE:  PauseState(),
    StateID.RESULT: ResultState(),
}

passed = 0
failed = 0

def test(name, actual, expected):
    global passed, failed
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if ok:
        passed += 1
    else:
        print(f"         expected {expected!r}, got {actual!r}")
        failed += 1

# ── 1. Config loading ──
print("Test 1: Config loaded from JSON")
from config import SCREEN_W, SCREEN_H, FIGHTER_W, MAX_HEALTH, MOVE_SPEED, \
    ATTACK_DAMAGE, GRAVITY, JUMP_SPEED
test("SCREEN_W=800", SCREEN_W, 800)
test("SCREEN_H=600", SCREEN_H, 600)
test("FIGHTER_W=50", FIGHTER_W, 50)
test("MAX_HEALTH=100", MAX_HEALTH, 100)
test("MOVE_SPEED=4.5", MOVE_SPEED, 4.5)
test("ATTACK_DAMAGE=8", ATTACK_DAMAGE, 8)
test("GRAVITY=0.7", GRAVITY, 0.7)
test("JUMP_SPEED=-16", JUMP_SPEED, -16.0)

# ── 2. KeyConfig from JSON ──
print("Test 2: KeyConfig built from config.json")
test("P1 A→MOVE_LEFT", Action.MOVE_LEFT in PLAYER1_KEY_CONFIG.actions_for(pygame.K_a), True)
test("P1 F→ATTACK", Action.ATTACK in PLAYER1_KEY_CONFIG.actions_for(pygame.K_f), True)
test("P2 LEFT→MOVE_LEFT", Action.MOVE_LEFT in PLAYER2_KEY_CONFIG.actions_for(pygame.K_LEFT), True)
test("P2 KP0→ATTACK", Action.ATTACK in PLAYER2_KEY_CONFIG.actions_for(pygame.K_KP0), True)
test("P1 ESC→PAUSE", Action.PAUSE in PLAYER1_KEY_CONFIG.actions_for(pygame.K_ESCAPE), True)
test("P1 ESC→CANCEL", Action.CANCEL in PLAYER1_KEY_CONFIG.actions_for(pygame.K_ESCAPE), True)

# ── 3. InputBuffer ──
print("Test 3: InputBuffer")
buf = InputBuffer()
buf.tick(); buf.push(Action.MOVE_RIGHT)
buf.tick(); buf.push(Action.MOVE_RIGHT)
buf.tick(); buf.push(Action.ATTACK)
test("[R,R,ATK]", buf.has_sequence([Action.MOVE_RIGHT, Action.MOVE_RIGHT, Action.ATTACK]), True)
test("[R,ATK]", buf.has_sequence([Action.MOVE_RIGHT, Action.ATTACK]), True)
test("no [L,ATK]", buf.has_sequence([Action.MOVE_LEFT, Action.ATTACK]), False)

# ── 4. InputManager idle ──
print("Test 4: InputManager idle")
mgr = InputManager(PLAYER1_KEY_CONFIG)
mgr.update()
test("is_held=False", mgr.is_held(Action.MOVE_LEFT), False)
test("just_pressed=False", mgr.just_pressed(Action.JUMP), False)
mgr.update()
test("frame2 just_pressed=False", mgr.just_pressed(Action.ATTACK), False)

# ── 5. State logic (without key input) ──
print("Test 5: State transitions")
ctx.p1, ctx.p2, ctx.round_timer = make_fighters()
ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG)
ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)
ctx.input_p1.update(); ctx.input_p2.update()
test("Menu stays", states[StateID.MENU].update(ctx), None)

ctx.p1, ctx.p2, ctx.round_timer = make_fighters()
ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG); ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)
ctx.input_p1.update(); ctx.input_p2.update()
test("Fight stays", states[StateID.FIGHT].update(ctx), None)

# ── 6. Attack collision ──
print("Test 6: Attack collision")
ctx.p1, ctx.p2, _ = make_fighters()
ctx.p2.x = ctx.p1.x + 55
ctx.p1.attack()
# 推进启动帧（startup=4）
for _ in range(4):
    check_attack(ctx.p1, ctx.p2)
    ctx.p1.update()
# 现在进入 active 阶段
check_attack(ctx.p1, ctx.p2)
test("P2 took damage", ctx.p2.health < MAX_HEALTH, True)

# ── 7. Game end ──
print("Test 7: Game end")
ctx.p1, ctx.p2, ctx.round_timer = make_fighters()
ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG); ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)
ctx.p2.dead = True
result = states[StateID.FIGHT].update(ctx)
test("P2 dead → RESULT", result, StateID.RESULT)

ctx.p1, ctx.p2, ctx.round_timer = make_fighters()
ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG); ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)
ctx.round_timer = 0
ctx.p1.health, ctx.p2.health = 55, 45
result = states[StateID.FIGHT].update(ctx)
test("Timeout → RESULT", result, StateID.RESULT)

# ── 8. Draw ──
print("Test 8: Draw")
ctx.p1, ctx.p2, ctx.round_timer = make_fighters()
for name, state in states.items():
    try:
        state.draw(ctx)
        test(f"draw {name}", True, True)
    except Exception as e:
        test(f"draw {name}", False, True)

# ── 9. Fighter uses config values ──
print("Test 9: Fighter respects config")
from fighter import Fighter as F
f = F(100, (255,0,0), (100,0,0), "test", True)
test("health=MAX_HEALTH", f.health, MAX_HEALTH)
f.move(1)
import math
test("moved by MOVE_SPEED", math.isclose(f.x, 100 + MOVE_SPEED), True)

print(f"\n{passed} passed, {failed} failed")
assert failed == 0
print("OK")
pygame.quit()
