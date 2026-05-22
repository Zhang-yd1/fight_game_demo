"""碰撞系统 — Hitbox / Hurtbox 分离"""

from dataclasses import dataclass, field
from typing import Optional
import pygame


@dataclass
class CollisionBox:
    """单个碰撞盒（坐标相对于战士原点，面向右时的定义）"""
    offset_x: float
    offset_y: float
    width: int
    height: int
    type: str = "hurt"  # "hit" | "hurt" | "throw" | "projectile"

    # ── 攻击属性（仅 type=="hit" 时有效）──
    damage: int = 0
    knockback_x: float = 0.0
    knockback_y: float = 0.0
    hitstun: int = 0
    blockstun: int = 0
    hitstop: int = 0
    chip_damage: int = 0
    # 命中后施加的自身硬直（用于 hitstop）
    attacker_hitstop: int = 0

    # ── 元数据 ──
    hit_id: int = 0  # 同一攻击技中区分不同 hitbox（防止同一招式多次命中）


def to_world_rect(box: CollisionBox, origin_x: float, origin_y: float,
                  facing_right: bool, fighter_w: int) -> pygame.Rect:
    """将相对碰撞盒转换为世界坐标矩形"""
    if facing_right:
        wx = origin_x + box.offset_x
    else:
        wx = origin_x + (fighter_w - box.offset_x - box.width)
    wy = origin_y + box.offset_y
    return pygame.Rect(int(wx), int(wy), box.width, box.height)


def check_hitbox_hurtbox(
    attacker_hitboxes: list[CollisionBox],
    defender_hurtboxes: list[CollisionBox],
    a_x: float, a_y: float, a_facing: bool, a_w: int,
    d_x: float, d_y: float, d_facing: bool, d_w: int,
) -> Optional[CollisionBox]:
    """
    检测攻击方的 hitbox 是否命中防守方的 hurtbox。
    返回首个命中的 hitbox（含伤害等数据），未命中返回 None。
    """
    for hb in attacker_hitboxes:
        hb_rect = to_world_rect(hb, a_x, a_y, a_facing, a_w)
        for hb2 in defender_hurtboxes:
            hb2_rect = to_world_rect(hb2, d_x, d_y, d_facing, d_w)
            if hb_rect.colliderect(hb2_rect):
                return hb
    return None