"""格斗游戏 — 主入口：状态机调度 + 主循环"""

import pygame
import sys

from config import SCREEN_W, SCREEN_H, FPS, WINDOW_TITLE, \
    PLAYER1_KEY_CONFIG, PLAYER2_KEY_CONFIG
from input_system import InputManager
from states import (
    GameContext, GameState,
    StateID,
    MenuState, FightState, PauseState, ResultState,
    make_fighters,
)


def main():
    # ── Pygame 初始化 ──
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    # ── 字体 ──
    fonts = {
        'hud':    pygame.font.SysFont("SimHei", 18, bold=True),
        'result': pygame.font.SysFont("SimHei", 56, bold=True),
        'hint':   pygame.font.SysFont("SimHei", 22),
        'guide':  pygame.font.SysFont("SimHei", 14),
    }

    # ── 创建上下文，注入输入管理器（使用配置文件中的键位）──
    ctx = GameContext(screen, clock, fonts)
    ctx.input_p1 = InputManager(PLAYER1_KEY_CONFIG)
    ctx.input_p2 = InputManager(PLAYER2_KEY_CONFIG)

    # ── 注册所有状态（单例）──
    states: dict[str, GameState] = {
        StateID.MENU:   MenuState(),
        StateID.FIGHT:  FightState(),
        StateID.PAUSE:  PauseState(),
        StateID.RESULT: ResultState(),
    }

    # ── 从主菜单启动 ──
    current_name = StateID.MENU
    current_state = states[current_name]
    current_state.on_enter(ctx)

    # ═══════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════
    while True:

        # ── 0. 全局事件（QUIT 统一处理）──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # ── 1. 更新输入（每个状态依赖此项）──
        ctx.input_p1.update()
        ctx.input_p2.update()

        # ── 2. 逻辑更新 → 可能触发状态切换 ──
        next_name = current_state.update(ctx)
        if next_name is not None:
            if not _transition(ctx, states, next_name, current_name):
                break
            current_name = next_name
            current_state = states[current_name]
            continue

        # ── 3. 绘制 ──
        current_state.draw(ctx)

        # ── 4. 刷新 & 限帧 ──
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


def _transition(ctx: GameContext, states: dict, next_name: str,
                current_name: str) -> bool:
    """执行状态切换，返回 True 表示切换成功，False 表示退出"""
    if next_name == StateID.QUIT:
        return False

    current_state = states[current_name]
    current_state.on_exit(ctx)

    # 进入「对战」前重置战士（从暂停恢复时不重置）
    if next_name == StateID.FIGHT and current_name != StateID.PAUSE:
        ctx.p1, ctx.p2, ctx.round_timer = make_fighters()

    next_state = states[next_name]
    next_state.on_enter(ctx)

    return True


if __name__ == "__main__":
    main()
