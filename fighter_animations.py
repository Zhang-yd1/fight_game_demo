"""战士动画 — 程序化绘制的帧函数 + 预定义动画"""

import pygame
from animation import AnimFrame, Anim, Animator
from config import FIGHTER_W, ATTACK_ARM_W, ATTACK_ARM_H, ATTACK_DAMAGE
from collision import CollisionBox


# ── 碰撞盒常量 ──

BODY_HURTBOX = CollisionBox(
    offset_x=10, offset_y=0, width=30, height=78, type="hurt",
)

ATTACK_HITBOX = CollisionBox(
    offset_x=50, offset_y=20, width=ATTACK_ARM_W, height=ATTACK_ARM_H,
    type="hit", damage=ATTACK_DAMAGE, knockback_x=3.0, knockback_y=-2.0,
    hitstun=16, blockstun=10, hitstop=8, hit_id=0,
)


# ═══════════════════════════════════════════════
# 底层绘制辅助
# ═══════════════════════════════════════════════

def _draw_body(surface, rx, ry, color, dark_color):
    pygame.draw.rect(surface, color, (rx + 10, ry + 25, 30, 35))
    pygame.draw.rect(surface, dark_color, (rx + 10, ry + 25, 30, 35), 2)


def _draw_head(surface, rx, ry, facing_right, color, dark_color):
    pygame.draw.circle(surface, color, (rx + 25, ry + 15), 15)
    pygame.draw.circle(surface, dark_color, (rx + 25, ry + 15), 15, 2)
    eye_off = 6 if facing_right else -6
    pygame.draw.circle(surface, dark_color, (rx + 25 + eye_off, ry + 12), 3)


def _draw_legs(surface, rx, ry, color, dark_color, leg_off=0):
    """leg_off: 交替偏移量，用于走路动画"""
    pygame.draw.rect(surface, color, (rx + 10,       ry + 58, 12, 22 + leg_off))
    pygame.draw.rect(surface, dark_color, (rx + 10,  ry + 58, 12, 22 + leg_off), 2)
    pygame.draw.rect(surface, color, (rx + 28,       ry + 58, 12, 22 - leg_off))
    pygame.draw.rect(surface, dark_color, (rx + 28,  ry + 58, 12, 22 - leg_off), 2)


def _draw_arms_down(surface, rx, ry, facing_right, color, dark_color):
    if facing_right:
        pygame.draw.rect(surface, color, (rx + 40, ry + 28, 10, 18))
        pygame.draw.rect(surface, dark_color, (rx + 40, ry + 28, 10, 18), 2)
    else:
        pygame.draw.rect(surface, color, (rx, ry + 28, 10, 18))
        pygame.draw.rect(surface, dark_color, (rx, ry + 28, 10, 18), 2)


def _draw_arms_attack(surface, rx, ry, facing_right, color, dark_color):
    """攻击时伸出的拳头"""
    if facing_right:
        arm_x = rx + FIGHTER_W
    else:
        arm_x = rx - ATTACK_ARM_W
    arm_y = ry + 20
    arm_rect = pygame.Rect(arm_x, arm_y, ATTACK_ARM_W, ATTACK_ARM_H)
    pygame.draw.rect(surface, color, arm_rect)
    pygame.draw.rect(surface, dark_color, arm_rect, 2)


# ═══════════════════════════════════════════════
# 各状态帧绘制函数
# ═══════════════════════════════════════════════

def draw_idle(surface, x, y, facing_right, color, dark_color, **_):
    """站立待机"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    _draw_legs(surface, x, y, color, dark_color, leg_off=0)
    _draw_arms_down(surface, x, y, facing_right, color, dark_color)


def draw_walk_1(surface, x, y, facing_right, color, dark_color, **_):
    """走路帧1：左腿前"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    _draw_legs(surface, x, y, color, dark_color, leg_off=3)
    _draw_arms_down(surface, x, y, facing_right, color, dark_color)


def draw_walk_2(surface, x, y, facing_right, color, dark_color, **_):
    """走路帧2：右腿前"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    _draw_legs(surface, x, y, color, dark_color, leg_off=-3)
    _draw_arms_down(surface, x, y, facing_right, color, dark_color)


def draw_jump(surface, x, y, facing_right, color, dark_color, **_):
    """跳跃：腿收拢"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    # 跳跃时腿短一些
    _draw_legs(surface, x, y, color, dark_color, leg_off=-6)
    _draw_arms_down(surface, x, y, facing_right, color, dark_color)


def draw_attack(surface, x, y, facing_right, color, dark_color, **_):
    """攻击：伸拳"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    _draw_legs(surface, x, y, color, dark_color, leg_off=0)
    _draw_arms_attack(surface, x, y, facing_right, color, dark_color)


def draw_hit_1(surface, x, y, facing_right, color, dark_color, **_):
    """受击帧1：高亮 + 后退"""
    offset_x = -4 if facing_right else 4
    _draw_body(surface, x + offset_x, y, color, dark_color)
    _draw_head(surface, x + offset_x, y, facing_right, color, dark_color)
    _draw_legs(surface, x + offset_x, y, color, dark_color, leg_off=0)
    _draw_arms_down(surface, x + offset_x, y, facing_right, color, dark_color)


def draw_hit_2(surface, x, y, facing_right, color, dark_color, **_):
    """受击帧2：正常位置高亮"""
    _draw_body(surface, x, y, color, dark_color)
    _draw_head(surface, x, y, facing_right, color, dark_color)
    _draw_legs(surface, x, y, color, dark_color, leg_off=0)
    _draw_arms_down(surface, x, y, facing_right, color, dark_color)


# ═══════════════════════════════════════════════
# 构建战士 Animator
# ═══════════════════════════════════════════════

def make_fighter_animator() -> Animator:
    """创建并返回预配置的战士 Animator"""
    animator = Animator()

    # 待机 — 单帧，长持续时间（无变化）
    animator.add("idle", Anim("idle", [
        AnimFrame(draw_idle, duration=60,
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=True))

    # 走路 — 两帧交替
    animator.add("walk", Anim("walk", [
        AnimFrame(draw_walk_1, duration=8,
                  hurtboxes=[BODY_HURTBOX]),
        AnimFrame(draw_walk_2, duration=8,
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=True))

    # 跳跃 — 单帧
    animator.add("jump", Anim("jump", [
        AnimFrame(draw_jump, duration=60,
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=True))

    # 攻击 — 伸拳后保持短暂时间
    animator.add("attack", Anim("attack", [
        AnimFrame(draw_attack, duration=12,
                  hitboxes=[ATTACK_HITBOX],
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=False))

    # 受击 — 高亮闪烁（2帧 × 4次 = 8帧闪烁）
    animator.add("hit", Anim("hit", [
        AnimFrame(draw_hit_1, duration=2,
                  hurtboxes=[BODY_HURTBOX]),
        AnimFrame(draw_hit_2, duration=2,
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=True))

    # 防御 — 目前复用空闲姿态（后续可替换为防御专属帧）
    animator.add("block", Anim("block", [
        AnimFrame(draw_idle, duration=60,
                  hurtboxes=[BODY_HURTBOX]),
    ], loop=True))

    animator.play("idle")
    return animator