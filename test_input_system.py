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
test("P1 J→LIGHT_PUNCH", Action.LIGHT_PUNCH in PLAYER1_KEY_CONFIG.actions_for(pygame.K_j), True)
test("P2 LEFT→MOVE_LEFT", Action.MOVE_LEFT in PLAYER2_KEY_CONFIG.actions_for(pygame.K_LEFT), True)
test("P2 KP1→LIGHT_PUNCH", Action.LIGHT_PUNCH in PLAYER2_KEY_CONFIG.actions_for(pygame.K_KP1), True)
test("P1 ESC→PAUSE", Action.PAUSE in PLAYER1_KEY_CONFIG.actions_for(pygame.K_ESCAPE), True)
test("P1 ESC→CANCEL", Action.CANCEL in PLAYER1_KEY_CONFIG.actions_for(pygame.K_ESCAPE), True)

# ── 3. InputBuffer ──
print("Test 3: InputBuffer")
buf = InputBuffer()
buf.tick(); buf.push(Action.MOVE_RIGHT)
buf.tick(); buf.push(Action.MOVE_RIGHT)
buf.tick(); buf.push(Action.LIGHT_PUNCH)
test("[R,R,LP]", buf.has_sequence([Action.MOVE_RIGHT, Action.MOVE_RIGHT, Action.LIGHT_PUNCH]), True)
test("[R,LP]", buf.has_sequence([Action.MOVE_RIGHT, Action.LIGHT_PUNCH]), True)
test("no [L,LP]", buf.has_sequence([Action.MOVE_LEFT, Action.LIGHT_PUNCH]), False)

# ── 4. InputManager idle ──
print("Test 4: InputManager idle")
mgr = InputManager(PLAYER1_KEY_CONFIG)
mgr.update()
test("is_held=False", mgr.is_held(Action.MOVE_LEFT), False)
test("just_pressed=False", mgr.just_pressed(Action.MOVE_UP), False)
mgr.update()
test("frame2 just_pressed=False", mgr.just_pressed(Action.LIGHT_PUNCH), False)

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

# ── 10. DirectionBuffer dash detection ──
print("Test 10: DirectionBuffer")
from input_system import DirectionBuffer
import input_system as inp_mod
inp_mod.DASH_INPUT_WINDOW = 20

db = DirectionBuffer()
db.tick(); db.push(Action.MOVE_RIGHT)
for _ in range(5):
    db.tick()
db.push(Action.MOVE_RIGHT)
test("→→ detected", db.check_dash(), 1)

db2 = DirectionBuffer()
db2.tick(); db2.push(Action.MOVE_LEFT)
for _ in range(5):
    db2.tick()
db2.push(Action.MOVE_LEFT)
test("←← detected", db2.check_dash(), -1)

db3 = DirectionBuffer()
db3.tick(); db3.push(Action.MOVE_RIGHT)
for _ in range(30):
    db3.tick()
db3.push(Action.MOVE_RIGHT)
test("→→ not detected (too far)", db3.check_dash(), None)

# ── 11. DirectionBuffer super jump ──
print("Test 11: Super jump detection")
db_sj = DirectionBuffer()
db_sj.tick(); db_sj.push(Action.MOVE_DOWN)
db_sj.tick(); db_sj.push(Action.MOVE_RIGHT)
db_sj.tick(); db_sj.push(Action.MOVE_UP)
test("↓→↑ detected", db_sj.check_super_jump(), True)

db_sj2 = DirectionBuffer()
db_sj2.tick(); db_sj2.push(Action.MOVE_DOWN)
db_sj2.tick(); db_sj2.push(Action.MOVE_LEFT)
db_sj2.tick(); db_sj2.push(Action.MOVE_UP)
test("↓←↑ not detected", db_sj2.check_super_jump(), False)

# ── 12. InputManager up-hold tracking ──
print("Test 12: Up-hold tracking")
mgr2 = InputManager(PLAYER1_KEY_CONFIG)
mgr2.update()
test("has dir_buffer", mgr2.dir_buffer is not None, True)
test("up_held_frames starts 0", mgr2.up_held_frames(), 0)
test("has frame_count", mgr2.frame_count > 0, True)

# ── 13. Fighter dash/backdash/hop mechanics ──
print("Test 13: Fighter movement mechanics")
f2 = F(200, (255, 0, 0), (100, 0, 0), "test2", False)
test("dash_timer starts 0", f2.dash_timer, 0)
test("_jump_type starts empty", f2._jump_type, "")
test("_dash_dir starts 0", f2._dash_dir, 0)

f2.start_dash()
test("dash_timer set", f2.dash_timer > 0, True)
test("_dash_dir = 1", f2._dash_dir, 1)
dash_vel = f2.vel_x
test("dash has velocity", abs(dash_vel) > 0, True)

f2.start_backdash()
test("backdash _dash_dir = -1", f2._dash_dir, -1)

f3 = F(300, (0, 255, 0), (0, 100, 0), "test3", True)
f3.start_hop()
test("hop _jump_type", f3._jump_type, "hop")
test("hop not on_ground", f3.on_ground, False)

f4 = F(400, (0, 0, 255), (0, 0, 100), "test4", True)
f4.start_super_jump()
test("super_jump _jump_type", f4._jump_type, "super")

# ── 14. FSM new states ──
print("Test 14: FSM recognizes new states")
from action_fsm import ActionState as AS
f5 = F(200, (255, 0, 0), (100, 0, 0), "test5", True)
f5.start_dash()
f5.fsm.sync(f5)
test("FSM sees DASH", f5.fsm.state, AS.DASH)

f6 = F(200, (255, 0, 0), (100, 0, 0), "test6", True)
f6.start_backdash()
f6.fsm.sync(f6)
test("FSM sees BACKDASH", f6.fsm.state, AS.BACKDASH)

f7 = F(200, (255, 0, 0), (100, 0, 0), "test7", True)
f7.start_hop()
f7.fsm.sync(f7)
test("FSM sees HOP", f7.fsm.state, AS.HOP)

f8 = F(200, (255, 0, 0), (100, 0, 0), "test8", True)
f8.start_super_jump()
f8.fsm.sync(f8)
test("FSM sees SUPER_JUMP", f8.fsm.state, AS.SUPER_JUMP)

# dash cancel tests
f_dc = F(200, (255, 0, 0), (100, 0, 0), "dc", True)
f_dc.start_dash()
f_dc.fsm.sync(f_dc)
test("can_dash_cancel on DASH", f_dc.fsm.can_dash_cancel(), True)

f_bd = F(200, (255, 0, 0), (100, 0, 0), "bd", True)
f_bd.start_backdash()
f_bd.fsm.sync(f_bd)
test("can_dash_cancel on BACKDASH", f_bd.fsm.can_dash_cancel(), True)

# airborne property
test("is_airborne HOP", AS.HOP.is_airborne, True)
test("is_airborne SUPER_JUMP", AS.SUPER_JUMP.is_airborne, True)
test("is_airborne JUMP", AS.JUMP.is_airborne, True)
test("is_airborne IDLE false", AS.IDLE.is_airborne, False)

# ── 15. Motion database ──
print("Test 15: Motion input database")
from motion_input import MOTION_DATABASE, check_special_move, MotionInput
test("database has entries", len(MOTION_DATABASE) > 0, True)
# qcf_p should exist
qcf = None
for m in MOTION_DATABASE:
    if m.name == "qcf_p":
        qcf = m
        break
test("qcf_p in database", qcf is not None, True)
if qcf:
    test("qcf_p motions", qcf.motions, [Action.MOVE_DOWN, Action.MOVE_RIGHT])
    test("qcf_p accepts P", Action.LIGHT_PUNCH in qcf.accept_buttons, True)
    test("qcf_p accepts K false", Action.LIGHT_KICK not in qcf.accept_buttons, True)

# ── 16. DirectionBuffer.has_motion_sequence ──
print("Test 16: Motion sequence detection")
dir_buf = DirectionBuffer()
dir_buf.tick(); dir_buf.push(Action.MOVE_DOWN)
dir_buf.tick(); dir_buf.push(Action.MOVE_RIGHT)
test("qcf [D,F] detected", dir_buf.has_motion_sequence(
    [Action.MOVE_DOWN, Action.MOVE_RIGHT], 15), True)

dir_buf2 = DirectionBuffer()
dir_buf2.tick(); dir_buf2.push(Action.MOVE_RIGHT)
dir_buf2.tick(); dir_buf2.push(Action.MOVE_DOWN)
dir_buf2.tick(); dir_buf2.push(Action.MOVE_RIGHT)
test("dp [F,D,F] detected", dir_buf2.has_motion_sequence(
    [Action.MOVE_RIGHT, Action.MOVE_DOWN, Action.MOVE_RIGHT], 12), True)

dir_buf3 = DirectionBuffer()
dir_buf3.tick(); dir_buf3.push(Action.MOVE_LEFT)
dir_buf3.tick(); dir_buf3.push(Action.MOVE_DOWN)
dir_buf3.tick(); dir_buf3.push(Action.MOVE_RIGHT)
test("hcb [L,D,R] detected", dir_buf3.has_motion_sequence(
    [Action.MOVE_LEFT, Action.MOVE_DOWN, Action.MOVE_RIGHT], 20), True)

# ── 17. Special move loading ──
print("Test 17: Special move loading")
from move_data import load_move
try:
    qcf_move = load_move("qcf_p")
    test("qcf_p loaded", True, True)
    test("qcf_p type special", qcf_move.move_type, "special")
    test("qcf_p meter_gain", qcf_move.meter_gain, 4)
    test("qcf_p meter_cost 0", qcf_move.meter_cost, 0)
except FileNotFoundError:
    test("qcf_p loaded", False, True)

try:
    dp_move = load_move("dp_p")
    test("dp_p loaded", True, True)
    # Check startup phase has invincible
    inv = dp_move.phases[0].invincible
    test("dp_p startup invincible", inv, True)
except FileNotFoundError:
    test("dp_p loaded", False, True)

# ── 18. Power gauge ──
print("Test 18: Power gauge")
f_pow = F(100, (255, 0, 0), (100, 0, 0), "pow", True)
test("power starts 0", f_pow.power_gauge, 0)
test("stocks starts 0", f_pow.power_stocks, 0)
test("max_mode starts False", f_pow.max_mode, False)

f_pow.add_meter(100)
test("add_meter 100", f_pow.power_gauge, 100)
test("stocks still 0 (< 128)", f_pow.power_stocks, 0)

f_pow.add_meter(30)
test("add_meter +30 = 130", f_pow.power_gauge, 130)
test("stocks = 1", f_pow.power_stocks, 1)

test("can_use_super 128", f_pow.can_use_super(128), True)
test("can_use_super 256 false", f_pow.can_use_super(256), False)

f_pow.consume_meter(128)
test("consume 128 → 2", f_pow.power_gauge, 2)

# ── 19. MAX mode ──
print("Test 19: MAX mode")
f_max = F(100, (255, 0, 0), (100, 0, 0), "max", True)
f_max.power_gauge = 128
f_max.health = 100  # full health, can't activate
test("MAX fail (full HP)", f_max.activate_max(), False)

f_max.health = 20  # ≤ 25%
result = f_max.activate_max()
test("MAX activate (20HP)", result, True)
test("MAX mode on", f_max.max_mode, True)
test("MAX timer set", f_max.max_timer > 0, True)
test("MAX gauge drained", f_max.power_gauge, 0)

# MAX mode damage reduction
f_def = F(100, (255, 0, 0), (100, 0, 0), "def", True)
f_def.max_mode = True
f_def.take_damage(50, hitstun=10)
test("MAX defense mult (<50)", f_def.health > 50, True)  # 50 * 0.75 = 37, health = 63

print(f"\n{passed} passed, {failed} failed")
assert failed == 0
print("OK")
pygame.quit()
