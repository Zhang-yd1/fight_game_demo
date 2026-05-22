"""格斗游戏 — 场景渲染（背景、HUD、结果画面）"""

import pygame
from config import (
    SCREEN_W, SCREEN_H, GROUND_Y, FPS, HUD_TOP_MARGIN, HUD_BAR_W,
    BLUE, RED, WHITE, YELLOW,
    METER_PER_STOCK, MAX_POWER_STOCKS, GREEN, ORANGE,
)
from fighter import Fighter


def draw_background(surface: pygame.Surface):
    """渐变天空、远景建筑、地面"""
    for y in range(GROUND_Y):
        ratio = y / GROUND_Y
        r = int(5 + ratio * 20)
        g = int(5 + ratio * 10)
        b = int(30 + ratio * 40)
        pygame.draw.line(surface, (r, g, b), (0, y), (SCREEN_W, y))

    buildings = [
        (50,  300, 80,  160),
        (160, 330, 60,  130),
        (260, 280, 100, 180),
        (400, 310, 70,  150),
        (510, 260, 90,  200),
        (640, 320, 75,  140),
        (730, 295, 70,  165),
    ]
    for bx, by, bw, bh in buildings:
        pygame.draw.rect(surface, (15, 15, 35), (bx, by, bw, bh))
        for wy in range(by + 10, by + bh - 10, 20):
            for wx in range(bx + 8, bx + bw - 8, 18):
                lit = (wx + wy) % 3 != 0
                wcolor = (200, 180, 80) if lit else (20, 20, 40)
                pygame.draw.rect(surface, wcolor, (wx, wy, 8, 10))

    pygame.draw.rect(surface, (30, 30, 30),
                     (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
    pygame.draw.rect(surface, (60, 60, 60),
                     (0, GROUND_Y, SCREEN_W, 4))


def draw_hud(surface: pygame.Surface,
             p1: Fighter, p2: Fighter,
             font: pygame.font.Font, round_time: int):
    """顶部 HUD：血量条 + 倒计时"""
    hud_h = HUD_TOP_MARGIN
    hud_surf = pygame.Surface((SCREEN_W, hud_h), pygame.SRCALPHA)
    hud_surf.fill((0, 0, 0, 160))
    surface.blit(hud_surf, (0, 0))

    p1_name = font.render(p1.name, True, BLUE)
    surface.blit(p1_name, (10, 5))
    p1.draw_health_bar(surface, 10, 28, flip=False)
    _draw_power_gauge(surface, p1, 10, 52, flip=False)

    p2_name = font.render(p2.name, True, RED)
    surface.blit(p2_name, (SCREEN_W - p2_name.get_width() - 10, 5))
    p2.draw_health_bar(surface, SCREEN_W - HUD_BAR_W - 10, 28, flip=True)
    _draw_power_gauge(surface, p2, SCREEN_W - HUD_BAR_W - 10, 52, flip=True)

    secs = max(0, round_time // FPS)
    timer_color = RED if secs <= 10 else WHITE
    timer_text = font.render(str(secs), True, timer_color)
    tx = SCREEN_W // 2 - timer_text.get_width() // 2
    surface.blit(timer_text, (tx, 10))


def draw_result(surface: pygame.Surface, message: str,
                big_font: pygame.font.Font, small_font: pygame.font.Font):
    """半透明结果面板"""
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surface.blit(overlay, (0, 0))

    title = big_font.render(message, True, YELLOW)
    tx = SCREEN_W // 2 - title.get_width() // 2
    surface.blit(title, (tx, SCREEN_H // 2 - 50))

    hint = small_font.render("按 R 重新开始  |  ESC 返回菜单", True, WHITE)
    hx = SCREEN_W // 2 - hint.get_width() // 2
    surface.blit(hint, (hx, SCREEN_H // 2 + 20))


def draw_menu(surface: pygame.Surface, fonts: dict):
    """主菜单画面"""
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    surface.blit(overlay, (0, 0))

    title = fonts['result'].render("格斗游戏", True, RED)
    tx = SCREEN_W // 2 - title.get_width() // 2
    surface.blit(title, (tx, SCREEN_H // 2 - 100))

    start = fonts['hint'].render("按 Enter 开始对战", True, YELLOW)
    sx = SCREEN_W // 2 - start.get_width() // 2
    surface.blit(start, (sx, SCREEN_H // 2))

    quit_hint = fonts['guide'].render("按 ESC 退出", True, WHITE)
    qx = SCREEN_W // 2 - quit_hint.get_width() // 2
    surface.blit(quit_hint, (qx, SCREEN_H // 2 + 60))


def _draw_power_gauge(surface: pygame.Surface, fighter,
                      bar_x: int, bar_y: int, flip: bool = False):
    """绘制能量槽圆点（KOF 风格）"""
    dot_r = 5
    gap = 6
    stocks = fighter.power_stocks
    max_stocks = MAX_POWER_STOCKS

    for i in range(max_stocks):
        dx = bar_x + i * (dot_r * 2 + gap) if not flip \
            else bar_x + HUD_BAR_W - (i + 1) * (dot_r * 2 + gap) + gap
        dy = bar_y
        filled = i < stocks
        # MAX 模式下闪烁
        if fighter.max_mode:
            filled = filled and (pygame.time.get_ticks() // 200) % 2 == 0
        color = YELLOW if filled else (60, 60, 60)
        if fighter.max_mode and filled:
            color = ORANGE
        pygame.draw.circle(surface, color, (dx + dot_r, dy + dot_r), dot_r)
        pygame.draw.circle(surface, (80, 80, 80), (dx + dot_r, dy + dot_r), dot_r, 1)

    # MAX 模式文字提示
    if fighter.max_mode:
        small = pygame.font.SysFont("Arial", 11, bold=True)
        txt = small.render("MAX", True, ORANGE)
        tx = bar_x + HUD_BAR_W + 8 if not flip else bar_x - txt.get_width() - 8
        surface.blit(txt, (tx, bar_y))


def draw_pause_overlay(surface: pygame.Surface, fonts: dict):
    """暂停覆盖层"""
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))

    title = fonts['result'].render("暂停中", True, YELLOW)
    tx = SCREEN_W // 2 - title.get_width() // 2
    surface.blit(title, (tx, SCREEN_H // 2 - 50))

    hint = fonts['hint'].render("ESC 继续  |  Q 返回菜单", True, WHITE)
    hx = SCREEN_W // 2 - hint.get_width() // 2
    surface.blit(hint, (hx, SCREEN_H // 2 + 20))
