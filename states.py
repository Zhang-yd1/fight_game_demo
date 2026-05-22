"""格斗游戏 — 游戏状态机（FSM）"""

from abc import ABC, abstractmethod
from typing import Optional
import pygame

from config import (
    SCREEN_W, SCREEN_H, FPS, ROUND_DURATION_SECS,
    BLUE, RED, DARK_BLUE, DARK_RED, GRAY,
    FIGHTER_W, HOP_THRESHOLD, HOP_VEL_Y,
    METER_GAIN_HIT, METER_GAIN_BLOCK,
    MAX_MODE_DAMAGE_MULT,
)
from fighter import Fighter
from input_system import Action
from collision import check_hitbox_hurtbox
from action_fsm import ActionState, TECH_RECOVERY
from motion_input import check_special_move
from render import (
    draw_background, draw_hud, draw_result,
    draw_menu, draw_pause_overlay,
)


# ── 状态标识 ──

class StateID:
    MENU   = "menu"
    FIGHT  = "fight"
    PAUSE  = "pause"
    RESULT = "result"
    QUIT   = "quit"


# ── 游戏上下文（状态间共享数据）──

class GameContext:
    """状态间共享的所有数据"""
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 fonts: dict):
        self.screen = screen
        self.clock  = clock
        self.fonts  = fonts
        self.input_p1 = None   # InputManager — 由 game.py 注入
        self.input_p2 = None
        self.p1: Fighter = None
        self.p2: Fighter = None
        self.round_timer = 0
        self.result_msg  = ""


# ── 状态基类 ──

class GameState(ABC):
    """
    每个具体状态实现：
      - update(ctx) → Optional[str]    逻辑更新，返回新状态ID触发切换
      - draw(ctx)                      绘制当前帧
      - on_enter(ctx) / on_exit(ctx)   生命周期回调
    """

    @abstractmethod
    def update(self, ctx: GameContext) -> Optional[str]:
        ...

    @abstractmethod
    def draw(self, ctx: GameContext):
        ...

    def on_enter(self, ctx: GameContext):
        pass

    def on_exit(self, ctx: GameContext):
        pass


# ── 工具函数 ──

def make_fighters() -> tuple:
    """创建两名新战士 + 重置倒计时"""
    p1 = Fighter(x=150, color=BLUE, dark_color=DARK_BLUE,
                 name="玩家1", facing_right=True)
    p2 = Fighter(x=600, color=RED, dark_color=DARK_RED,
                 name="玩家2", facing_right=False)
    timer = ROUND_DURATION_SECS * FPS
    return p1, p2, timer


def check_attack(attacker: Fighter, defender: Fighter):
    """每帧：检查攻击方 active 阶段的 hitbox 是否命中防守方 hurtbox"""
    if attacker.current_move is None:
        return
    if not attacker.current_move.is_active(attacker.move_frame):
        return

    hitbox = check_hitbox_hurtbox(
        attacker.current_hitboxes, defender.current_hurtboxes,
        attacker.x, attacker.y, attacker.facing_right, FIGHTER_W,
        defender.x, defender.y, defender.facing_right, FIGHTER_W,
    )
    if hitbox is None:
        return
    # 防止同一 hit_id 在本次招式中重复命中
    if hitbox.hit_id in attacker.connected_hit_ids:
        return

    attacker.connected_hit_ids.add(hitbox.hit_id)

    # MAX 模式攻击力加成
    damage = hitbox.damage
    if attacker.max_mode:
        damage = max(1, int(damage * MAX_MODE_DAMAGE_MULT))

    # 击退方向：始终远离攻击方面向
    kb_x = hitbox.knockback_x if attacker.facing_right else -hitbox.knockback_x

    if defender.is_blocking:
        defender.apply_block(hitbox)
        # 防御涨气
        defender.add_meter(METER_GAIN_BLOCK)
        attacker.add_meter(METER_GAIN_BLOCK // 2)
        a_stop = hitbox.attacker_hitstop if hitbox.attacker_hitstop > 0 else hitbox.hitstop
        attacker.hitstop = max(1, a_stop // 2)
        defender.hitstop = max(1, hitbox.hitstop // 2)
    else:
        defender.take_damage(
            damage, hitbox.hitstun,
            kb_x, hitbox.knockback_y, hitbox.hitstop,
        )
        # 命中涨气
        attacker.add_meter(METER_GAIN_HIT)
        a_stop = hitbox.attacker_hitstop if hitbox.attacker_hitstop > 0 else hitbox.hitstop
        attacker.hitstop = a_stop


# ═══════════════════════════════════════════════
# 具体状态类
# ═══════════════════════════════════════════════

class MenuState(GameState):
    """主菜单"""

    def update(self, ctx: GameContext) -> Optional[str]:
        if ctx.input_p1.just_pressed(Action.CONFIRM) \
                or ctx.input_p2.just_pressed(Action.CONFIRM):
            return StateID.FIGHT
        if ctx.input_p1.just_pressed(Action.CANCEL) \
                or ctx.input_p2.just_pressed(Action.CANCEL):
            return StateID.QUIT
        return None

    def draw(self, ctx: GameContext):
        draw_background(ctx.screen)
        draw_menu(ctx.screen, ctx.fonts)


class FightState(GameState):
    """对战进行中"""

    def _handle_player_input(self, player: Fighter, inp: 'InputManager',
                              opponent: Fighter):
        """处理单个玩家的输入（移动 / 跳跃 / 攻击）"""
        # ── dash / backdash 检测（仅在方向键刚按下时触发）──
        if player.fsm.can_move():
            if inp.just_pressed(Action.MOVE_RIGHT) or inp.just_pressed(Action.MOVE_LEFT):
                dash_dir = inp.dir_buffer.check_dash()
                if dash_dir == 1:
                    player.start_dash()
                elif dash_dir == -1:
                    player.start_backdash()

        # ── 移动：IDLE / WALK / BLOCK 状态允许 ──
        if player.fsm.can_move():
            if inp.is_held(Action.MOVE_LEFT):
                player.move(-1)
            if inp.is_held(Action.MOVE_RIGHT):
                player.move(+1)

        # ── 跳跃：可行动时（含蹲姿）──
        if player.is_actionable():
            if inp.just_pressed(Action.MOVE_UP):
                # 先检查 super jump（↓→↑）
                if inp.dir_buffer.check_super_jump():
                    player.start_super_jump()
                else:
                    player.jump()

        # ── 跳跃变体：松开上方向时根据按住帧数判定 hop ──
        if not player.on_ground and player._jump_type == "":
            if inp.just_released(Action.MOVE_UP):
                held = inp.up_held_frames()
                if 0 < held <= HOP_THRESHOLD:
                    player._jump_type = "hop"
                    player.vel_y = HOP_VEL_Y

        # ── MAX 发动（A+B+C）──
        if player.is_actionable():
            if inp.just_pressed(Action.MAX_ACTIVATE):
                player.activate_max()

        # ── 攻击（必杀技优先检测）──
        if player.is_actionable() or player.fsm.can_dash_cancel():
            for btn in (Action.LIGHT_PUNCH, Action.LIGHT_KICK,
                        Action.HEAVY_PUNCH, Action.HEAVY_KICK):
                if not inp.just_pressed(btn):
                    continue
                # 先检测必杀技指令
                special = check_special_move(inp.buffer, inp.dir_buffer, btn)
                if special is not None:
                    player.start_special(special)
                else:
                    btn_map = {Action.LIGHT_PUNCH: "a", Action.LIGHT_KICK: "b",
                               Action.HEAVY_PUNCH: "c", Action.HEAVY_KICK: "d"}
                    player.attack(btn_map[btn])

    def update(self, ctx: GameContext) -> Optional[str]:
        p1 = ctx.input_p1
        p2 = ctx.input_p2

        # ── 系统动作 ──
        if p1.just_pressed(Action.PAUSE) or p2.just_pressed(Action.PAUSE):
            return StateID.PAUSE

        # ── 玩家输入 ──
        self._handle_player_input(ctx.p1, ctx.input_p1, ctx.p2)
        self._handle_player_input(ctx.p2, ctx.input_p2, ctx.p1)

        # ── 防御 / 蹲姿判定（必须在碰撞检测之前）──
        ctx.p1.check_blocking(
            ctx.p2.x,
            p1.is_held(Action.MOVE_LEFT),
            p1.is_held(Action.MOVE_RIGHT),
            p1.is_held(Action.MOVE_DOWN),
        )
        ctx.p2.check_blocking(
            ctx.p1.x,
            p2.is_held(Action.MOVE_LEFT),
            p2.is_held(Action.MOVE_RIGHT),
            p2.is_held(Action.MOVE_DOWN),
        )

        # ── 碰撞检测（必须在 update 之前）──
        check_attack(ctx.p1, ctx.p2)
        check_attack(ctx.p2, ctx.p1)

        # ── 物理更新 ──
        ctx.p1.update()
        ctx.p2.update()

        # ── 朝向强制面对面 ──
        if ctx.p1.x < ctx.p2.x:
            ctx.p1.facing_right = True
            ctx.p2.facing_right = False
        else:
            ctx.p1.facing_right = False
            ctx.p2.facing_right = True

        # ── 受身检测 ──
        ctx.p1.try_tech(p1.is_held(Action.MOVE_LEFT) or p1.is_held(Action.MOVE_RIGHT))
        ctx.p2.try_tech(p2.is_held(Action.MOVE_LEFT) or p2.is_held(Action.MOVE_RIGHT))

        # ── 倒计时 ──
        ctx.round_timer -= 1

        # ── 胜负判定 ──
        if ctx.p1.dead and ctx.p2.dead:
            ctx.result_msg = "平局！"
            return StateID.RESULT
        elif ctx.p1.dead:
            ctx.result_msg = "玩家2 获胜！"
            return StateID.RESULT
        elif ctx.p2.dead:
            ctx.result_msg = "玩家1 获胜！"
            return StateID.RESULT
        elif ctx.round_timer <= 0:
            if ctx.p1.health > ctx.p2.health:
                ctx.result_msg = "玩家1 获胜（时间到）！"
            elif ctx.p2.health > ctx.p1.health:
                ctx.result_msg = "玩家2 获胜（时间到）！"
            else:
                ctx.result_msg = "平局（时间到）！"
            return StateID.RESULT

        return None

    def draw(self, ctx: GameContext):
        draw_background(ctx.screen)
        ctx.p1.draw(ctx.screen)
        ctx.p2.draw(ctx.screen)
        draw_hud(ctx.screen, ctx.p1, ctx.p2, ctx.fonts['hud'], ctx.round_timer)

        guide = ctx.fonts['guide'].render(
            "P1: WASD移动 J=LP K=LK U=HP I=HK    P2: 方向键移动 小键盘1=LP 2=LK 4=HP 5=HK",
            True, GRAY)
        ctx.screen.blit(guide, (
            SCREEN_W // 2 - guide.get_width() // 2,
            SCREEN_H - 22))


class PauseState(GameState):
    """暂停画面"""

    def update(self, ctx: GameContext) -> Optional[str]:
        if ctx.input_p1.just_pressed(Action.CANCEL) \
                or ctx.input_p2.just_pressed(Action.CANCEL):
            return StateID.FIGHT
        if ctx.input_p1.just_pressed(Action.QUIT_TO_MENU) \
                or ctx.input_p2.just_pressed(Action.QUIT_TO_MENU):
            return StateID.MENU
        return None

    def draw(self, ctx: GameContext):
        draw_background(ctx.screen)
        ctx.p1.draw(ctx.screen)
        ctx.p2.draw(ctx.screen)
        draw_hud(ctx.screen, ctx.p1, ctx.p2, ctx.fonts['hud'], ctx.round_timer)
        draw_pause_overlay(ctx.screen, ctx.fonts)


class ResultState(GameState):
    """结果画面"""

    def update(self, ctx: GameContext) -> Optional[str]:
        if ctx.input_p1.just_pressed(Action.REMATCH) \
                or ctx.input_p2.just_pressed(Action.REMATCH):
            return StateID.FIGHT
        if ctx.input_p1.just_pressed(Action.CANCEL) \
                or ctx.input_p2.just_pressed(Action.CANCEL):
            return StateID.MENU
        return None

    def draw(self, ctx: GameContext):
        draw_background(ctx.screen)
        ctx.p1.draw(ctx.screen)
        ctx.p2.draw(ctx.screen)
        draw_hud(ctx.screen, ctx.p1, ctx.p2, ctx.fonts['hud'], ctx.round_timer)
        draw_result(ctx.screen, ctx.result_msg,
                    ctx.fonts['result'], ctx.fonts['hint'])
