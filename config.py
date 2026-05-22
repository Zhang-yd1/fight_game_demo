"""从 data/config.json 加载配置，提供模块级常量访问"""

import json
import os
import pygame

# ── 加载 JSON ──

_path = os.path.join(os.path.dirname(__file__), 'data', 'config.json')
with open(_path, 'r', encoding='utf-8') as f:
    _cfg = json.load(f)

# ── 窗口 ──

SCREEN_W     = _cfg['window']['width']
SCREEN_H     = _cfg['window']['height']
WINDOW_TITLE = _cfg['window']['title']
FPS          = _cfg['window']['fps']

# ── 颜色（list → tuple）──

def _rgb(key: str) -> tuple:
    return tuple(_cfg['colors'][key])

BLACK      = _rgb('black')
WHITE      = _rgb('white')
RED        = _rgb('red')
BLUE       = _rgb('blue')
DARK_RED   = _rgb('dark_red')
DARK_BLUE  = _rgb('dark_blue')
GRAY       = _rgb('gray')
DARK_GRAY  = _rgb('dark_gray')
YELLOW     = _rgb('yellow')
GREEN      = _rgb('green')
ORANGE     = _rgb('orange')

# ── 地面 ──

GROUND_Y = _cfg['ground']['y']

# ── 物理 ──

GRAVITY    = _cfg['physics']['gravity']
JUMP_SPEED = _cfg['physics']['jump_speed']

# ── 战士 ──

FIGHTER_W   = _cfg['fighter']['width']
FIGHTER_H   = _cfg['fighter']['height']
MAX_HEALTH  = _cfg['fighter']['max_health']
MOVE_SPEED  = _cfg['fighter']['move_speed']

# ── 攻击 ──

ATTACK_DAMAGE       = _cfg['attack']['damage']
ATTACK_DURATION     = _cfg['attack']['duration_frames']
ATTACK_COOLDOWN     = _cfg['attack']['cooldown_frames']
ATTACK_ARM_W        = _cfg['attack']['arm_width']
ATTACK_ARM_H        = _cfg['attack']['arm_height']
HIT_FLASH_FRAMES    = _cfg['attack']['hit_flash_frames']

# ── 防御 ──

MAX_BLOCK_HEALTH    = _cfg['block']['max_block_health']
CHIP_DAMAGE_RATIO   = _cfg['block']['chip_damage_ratio']
GUARD_BREAK_STUN    = _cfg['block']['guard_break_stun']

# ── 回合 ──

ROUND_DURATION_SECS = _cfg['round']['duration_secs']

# ── HUD ──

HUD_BAR_W      = _cfg['hud']['bar_width']
HUD_BAR_H      = _cfg['hud']['bar_height']
HUD_TOP_MARGIN = _cfg['hud']['top_margin']


# ── 按键 → Pygame keycode 映射 ──

_KEY_MAP: dict[str, int] = {
    'a': pygame.K_a, 'b': pygame.K_b, 'c': pygame.K_c, 'd': pygame.K_d,
    'e': pygame.K_e, 'f': pygame.K_f, 'g': pygame.K_g, 'h': pygame.K_h,
    'i': pygame.K_i, 'j': pygame.K_j, 'k': pygame.K_k, 'l': pygame.K_l,
    'm': pygame.K_m, 'n': pygame.K_n, 'o': pygame.K_o, 'p': pygame.K_p,
    'q': pygame.K_q, 'r': pygame.K_r, 's': pygame.K_s, 't': pygame.K_t,
    'u': pygame.K_u, 'v': pygame.K_v, 'w': pygame.K_w, 'x': pygame.K_x,
    'y': pygame.K_y, 'z': pygame.K_z,
    '0': pygame.K_0, '1': pygame.K_1, '2': pygame.K_2, '3': pygame.K_3,
    '4': pygame.K_4, '5': pygame.K_5, '6': pygame.K_6, '7': pygame.K_7,
    '8': pygame.K_8, '9': pygame.K_9,
    'escape': pygame.K_ESCAPE, 'return': pygame.K_RETURN,
    'space':  pygame.K_SPACE,  'tab':    pygame.K_TAB,
    'up':     pygame.K_UP,     'down':   pygame.K_DOWN,
    'left':   pygame.K_LEFT,   'right':  pygame.K_RIGHT,
    'kp0': pygame.K_KP0, 'kp1': pygame.K_KP1, 'kp2': pygame.K_KP2,
    'kp3': pygame.K_KP3, 'kp4': pygame.K_KP4, 'kp5': pygame.K_KP5,
    'kp6': pygame.K_KP6, 'kp7': pygame.K_KP7, 'kp8': pygame.K_KP8,
    'kp9': pygame.K_KP9,
    'lshift': pygame.K_LSHIFT, 'rshift': pygame.K_RSHIFT,
    'lctrl':  pygame.K_LCTRL,  'rctrl':  pygame.K_RCTRL,
    'lalt':   pygame.K_LALT,   'ralt':   pygame.K_RALT,
}


def _parse_key_name(name: str) -> int:
    key = _KEY_MAP.get(name.lower())
    if key is None:
        raise ValueError(f"Unknown key name in config: '{name}'")
    return key


# ── 从配置构建 KeyConfig ──

from input_system import KeyConfig


def _build_key_config(player_key: str) -> KeyConfig:
    bindings = _cfg['keybinds'][player_key]
    return KeyConfig(**{
        action.upper(): _parse_key_name(key_name)
        for action, key_name in bindings.items()
    })


PLAYER1_KEY_CONFIG = _build_key_config('player1')
PLAYER2_KEY_CONFIG = _build_key_config('player2')
