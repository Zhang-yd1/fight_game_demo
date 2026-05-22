"""格斗游戏 — 游戏状态机（FSM）"""

from abc import ABC, abstractmethod
from typing import Optional
import pygame

from config import (
    SCREEN_W, SCREEN_H, FPS, ROUND_DURATION_SECS,
    BLUE, RED, DARK_BLUE, DARK_RED, GRAY,
    ATTACK_DAMAGE, ATTACK_DURATION, FIGHTER_W,
)
from fighter import Fighter
from input_system import Action
from collision import check_hitbox_hurtbox
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
    """攻击首帧：hitbox ∩ hurtbox 碰撞检测，处理防御/命中"""
    if attacker.attack_timer != ATTACK_DURATION:
        return
    hitbox = check_hitbox_hurtbox(
        attacker.current_hitboxes, defender.current_hurtboxes,
        attacker.x, attacker.y, attacker.facing_right, FIGHTER_W,
        defender.x, defender.y, defender.facing_right, FIGHTER_W,
    )
    if hitbox is None:
        return
    if defender.is_blocking:
        defender.apply_block(hitbox)
    else:
        defender.take_damage(hitbox.damage)


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

    def update(self, ctx: GameContext) -> Optional[str]:
        p1 = ctx.input_p1
        p2 = ctx.input_p2

        # ── 系统动作 ──
        if p1.just_pressed(Action.PAUSE) or p2.just_pressed(Action.PAUSE):
            return StateID.PAUSE

        # ── 玩家1 输入（硬直中不可行动）──
        if ctx.p1.is_actionable():
            if p1.is_held(Action.MOVE_LEFT):
                ctx.p1.move(-1)
            if p1.is_held(Action.MOVE_RIGHT):
                ctx.p1.move(+1)
            if p1.just_pressed(Action.JUMP):
                ctx.p1.jump()
            if p1.is_held(Action.ATTACK):
                ctx.p1.attack()

        # ── 玩家2 输入 ──
        if ctx.p2.is_actionable():
            if p2.is_held(Action.MOVE_LEFT):
                ctx.p2.move(-1)
            if p2.is_held(Action.MOVE_RIGHT):
                ctx.p2.move(+1)
            if p2.just_pressed(Action.JUMP):
                ctx.p2.jump()
            if p2.is_held(Action.ATTACK):
                ctx.p2.attack()

        # ── 防御判定（必须在碰撞检测之前）──
        ctx.p1.check_blocking(
            ctx.p2.x,
            p1.is_held(Action.MOVE_LEFT),
            p1.is_held(Action.MOVE_RIGHT),
        )
        ctx.p2.check_blocking(
            ctx.p1.x,
            p2.is_held(Action.MOVE_LEFT),
            p2.is_held(Action.MOVE_RIGHT),
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
            "玩家1: A/D 移动  W 跳  F 攻击      玩家2: ←/→ 移动  ↑ 跳  小键盘0 攻击",
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
