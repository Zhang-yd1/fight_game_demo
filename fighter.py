"""格斗游戏 — Fighter 类"""

import pygame
from config import (
    FIGHTER_W, FIGHTER_H, GROUND_Y, SCREEN_W, SCREEN_H,
    GRAVITY, JUMP_SPEED, MAX_HEALTH, MOVE_SPEED,
    ATTACK_DURATION, ATTACK_COOLDOWN,
    HIT_FLASH_FRAMES, HUD_BAR_W, HUD_BAR_H,
    MAX_BLOCK_HEALTH, CHIP_DAMAGE_RATIO, GUARD_BREAK_STUN,
    WHITE, DARK_GRAY, GREEN, YELLOW, ORANGE, GRAY,
)
from animation import Animator
from fighter_animations import make_fighter_animator
from collision import CollisionBox


class Fighter:
    """表示一名像素风格战士"""

    def __init__(self, x: int, color: tuple, dark_color: tuple,
                 name: str, facing_right: bool):
        self.name = name
        self.color = color
        self.dark_color = dark_color

        self.x = float(x)
        self.y = float(GROUND_Y - FIGHTER_H)
        self.vel_x = 0.0
        self.vel_y = 0.0

        self.on_ground = True
        self.facing_right = facing_right

        self.health = MAX_HEALTH
        self.attack_timer = 0
        self.attack_cooldown = 0
        self.hit_flash = 0
        self.dead = False

        # ── 防御系统 ──
        self.is_blocking = False      # 本帧是否处于防御姿态
        self.blockstun = 0            # 防御硬直（不可行动）
        self.block_health = MAX_BLOCK_HEALTH
        self.guard_broken = False

        # 动画系统
        self.animator: Animator = make_fighter_animator()
        self._prev_x = self.x
        self._moving = False

    # ── 碰撞矩形 ──

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), FIGHTER_W, FIGHTER_H)

    @property
    def current_hitboxes(self) -> list:
        """当前帧的 hitbox 列表"""
        frame = self.animator.current_frame
        if frame is None:
            return []
        return frame.hitboxes

    @property
    def current_hurtboxes(self) -> list:
        """当前帧的 hurtbox 列表"""
        frame = self.animator.current_frame
        if frame is None:
            return []
        return frame.hurtboxes

    # ── 物理 ──

    def apply_gravity(self):
        if not self.on_ground:
            self.vel_y += GRAVITY
        self.y += self.vel_y
        ground_surface_y = GROUND_Y - FIGHTER_H
        if self.y >= ground_surface_y:
            self.y = ground_surface_y
            self.vel_y = 0
            self.on_ground = True

    def clamp_to_screen(self):
        self.x = max(0.0, min(float(SCREEN_W - FIGHTER_W), self.x))

    # ── 动作 ──

    def move(self, direction: int):
        self.x += direction * MOVE_SPEED
        self.facing_right = (direction > 0)

    def jump(self):
        if self.on_ground:
            self.vel_y = JUMP_SPEED
            self.on_ground = False

    def attack(self):
        if self.attack_cooldown == 0 and self.attack_timer == 0:
            self.attack_timer = ATTACK_DURATION
            self.attack_cooldown = ATTACK_COOLDOWN
            self.animator.play("attack")

    def take_damage(self, amount: int):
        if self.dead:
            return
        self.health = max(0, self.health - amount)
        self.hit_flash = HIT_FLASH_FRAMES
        if self.health == 0:
            self.dead = True

    # ── 防御系统 ──

    def is_actionable(self) -> bool:
        """是否可行动（不在任何硬直中）"""
        return (self.blockstun == 0
                and self.attack_timer == 0
                and not self.dead
                and not self.guard_broken)

    def check_blocking(self, attacker_x: float,
                       holding_left: bool, holding_right: bool):
        """每帧在碰撞检测前调用，更新防御姿态"""
        if self.is_blocking:
            # 切回站立姿态重新判定（blockstun 结束后需要）
            self.is_blocking = False

        if not self.on_ground:
            return
        if self.blockstun > 0:
            return
        if self.guard_broken:
            return

        holding_back = False
        if attacker_x > self.x and holding_left:
            holding_back = True
        elif attacker_x < self.x and holding_right:
            holding_back = True

        if holding_back:
            self.is_blocking = True

    def apply_block(self, hitbox) -> bool:
        """
        防御成功。返回 True 表示破防。
        hitbox 为 CollisionBox，从中读取 chip_damage / blockstun。
        """
        chip = hitbox.chip_damage if hitbox.chip_damage > 0 \
            else max(1, int(hitbox.damage * CHIP_DAMAGE_RATIO))
        self.health = max(0, self.health - chip)
        self.blockstun = max(1, hitbox.blockstun)
        self.block_health = max(0, self.block_health - hitbox.damage)
        self.hit_flash = HIT_FLASH_FRAMES

        if self.block_health == 0:
            self.guard_broken = True
            self.blockstun = GUARD_BREAK_STUN
            self.is_blocking = False
            return True
        return False

    # ── 每帧更新 ──

    def update(self):
        self.apply_gravity()
        self.x += self.vel_x
        self.clamp_to_screen()

        # 移动检测（用于走路动画）
        self._moving = abs(self.x - self._prev_x) > 0.01
        self._prev_x = self.x

        # 递减计时器
        if self.attack_timer > 0:
            self.attack_timer -= 1
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.blockstun > 0:
            self.blockstun -= 1
            if self.blockstun == 0 and self.guard_broken:
                # 破防大硬直结束，恢复防御槽
                self.guard_broken = False
                self.block_health = MAX_BLOCK_HEALTH

        # 推进动画
        self.animator.tick()

    # ── 绘制 ──

    def _anim_state(self) -> str:
        """根据 Fighter 状态返回动画名"""
        if self.hit_flash > 0:
            return "hit"
        if self.attack_timer > 0:
            return "attack"
        if self.blockstun > 0:
            return "hit"
        if not self.on_ground:
            return "jump"
        if self.is_blocking:
            return "block"
        if self._moving:
            return "walk"
        return "idle"

    def draw(self, surface: pygame.Surface):
        # 受击闪烁：偶数帧用白色
        flashing = self.hit_flash > 0 and self.hit_flash % 2 == 0
        use_color = WHITE if flashing else self.color
        use_dark  = WHITE if flashing else self.dark_color

        state = self._anim_state()
        self.animator.play(state)
        self.animator.draw(surface, self.x, self.y, self.facing_right,
                           color=use_color, dark_color=use_dark)

    # ── 血量条 ──

    def draw_health_bar(self, surface: pygame.Surface,
                        bar_x: int, bar_y: int, flip: bool = False):
        bar_w, bar_h = HUD_BAR_W, HUD_BAR_H
        pygame.draw.rect(surface, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h))

        ratio = self.health / MAX_HEALTH
        hp_w = int(bar_w * ratio)

        if ratio > 0.5:
            hp_color = GREEN
        elif ratio > 0.25:
            hp_color = YELLOW
        else:
            hp_color = ORANGE

        if flip:
            pygame.draw.rect(surface, hp_color,
                             (bar_x + bar_w - hp_w, bar_y, hp_w, bar_h))
        else:
            pygame.draw.rect(surface, hp_color,
                             (bar_x, bar_y, hp_w, bar_h))

        pygame.draw.rect(surface, GRAY, (bar_x, bar_y, bar_w, bar_h), 2)

        font_small = pygame.font.SysFont("Arial", 14, bold=True)
        hp_text = font_small.render(f"{self.health}", True, WHITE)
        text_x = bar_x + bar_w // 2 - hp_text.get_width() // 2
        surface.blit(hp_text, (text_x, bar_y + 3))