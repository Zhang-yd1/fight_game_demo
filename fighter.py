"""格斗游戏 — Fighter 类"""

import pygame
from config import (
    FIGHTER_W, FIGHTER_H, GROUND_Y, SCREEN_W, SCREEN_H,
    GRAVITY, JUMP_SPEED, MAX_HEALTH, MOVE_SPEED,
    ATTACK_COOLDOWN,
    HIT_FLASH_FRAMES, HUD_BAR_W, HUD_BAR_H,
    MAX_BLOCK_HEALTH, CHIP_DAMAGE_RATIO, GUARD_BREAK_STUN,
    KNOCKBACK_FRICTION, KNOCKBACK_CORNER_MARGIN, KNOCKBACK_CORNER_FACTOR,
    DASH_SPEED, DASH_DURATION, BACKDASH_DURATION, BACKDASH_INVULN,
    HOP_VEL_Y, SUPER_JUMP_VEL_Y, HOP_THRESHOLD,
    METER_PER_STOCK, MAX_POWER_STOCKS,
    METER_GAIN_HIT, METER_GAIN_GOT_HIT, METER_GAIN_BLOCK, METER_GAIN_SPECIAL, METER_GAIN_WALK,
    MAX_MODE_DURATION, MAX_MODE_DAMAGE_MULT, MAX_MODE_DEFENSE_MULT,
    MAX_HEALTH_THRESHOLD,
    WHITE, DARK_GRAY, GREEN, YELLOW, ORANGE, GRAY,
)
from animation import Animator
from fighter_animations import make_fighter_animator
from collision import CollisionBox
from move_data import MoveData, DEFAULT_MOVE, load_move
from action_fsm import ActionFSM, ActionState, TECH_WINDOW, TECH_RECOVERY


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
        self.attack_cooldown = 0
        self.hit_flash = 0
        self.dead = False

        # ── 帧数据 / 招式状态机 ──
        self.current_move: MoveData | None = None
        self.move_frame = 0                     # 当前招式内的帧号（0-indexed）
        self.connected_hit_ids: set[int] = set()  # 本次招式已命中的 hit_id

        # ── 防御系统 ──
        self.is_blocking = False
        self.is_crouching = False
        self.is_crouch_blocking = False
        self.blockstun = 0
        self.block_health = MAX_BLOCK_HEALTH
        self.guard_broken = False

        # ── 硬直系统 ──
        self.hitstun = 0
        self.hitstop = 0
        self.knockback_vel = 0.0

        # 动作状态机
        self.fsm = ActionFSM()

        # ── 移动系统 ──
        self.dash_timer = 0          # dash/backdash 剩余帧数
        self._dash_dir = 0           # 1=前冲, -1=后撤步
        self._jump_type: str = ""    # "hop" / "super" / "" → normal jump

        # ── 能量系统 ──
        self.power_gauge: int = 0           # 0 ~ METER_PER_STOCK * MAX_POWER_STOCKS
        self.max_mode: bool = False          # MAX 状态
        self.max_timer: int = 0              # MAX 剩余帧数

        # 动画系统
        self.animator: Animator = make_fighter_animator()
        self._prev_x = self.x
        self._moving = False

    # ── 碰撞矩形 ──

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), FIGHTER_W, FIGHTER_H)

    @property
    def attack_timer(self) -> int:
        """向后兼容：返回当前招式的剩余帧数"""
        if self.current_move is None:
            return 0
        return self.current_move.total_frames - self.move_frame

    @property
    def current_hitboxes(self) -> list:
        """当前帧的 hitbox 列表"""
        if self.current_move is not None:
            phase = self.current_move.get_phase(self.move_frame)
            if phase is not None and phase.stage == "active":
                return phase.hitboxes
            return []
        frame = self.animator.current_frame
        return frame.hitboxes if frame else []

    @property
    def current_hurtboxes(self) -> list:
        """当前帧的 hurtbox 列表"""
        if self.current_move is not None:
            phase = self.current_move.get_phase(self.move_frame)
            if phase is not None:
                return phase.hurtboxes
            return []
        frame = self.animator.current_frame
        return frame.hurtboxes if frame else []

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
        else:
            self.on_ground = False

    def clamp_to_screen(self):
        self.x = max(0.0, min(float(SCREEN_W - FIGHTER_W), self.x))

    # ── 动作 ──

    def move(self, direction: int):
        self.x += direction * MOVE_SPEED
        self.facing_right = (direction > 0)

    def jump(self):
        """普跳：标准跳跃"""
        if self.on_ground:
            self._jump_type = ""
            self.vel_y = JUMP_SPEED
            self.on_ground = False

    def start_hop(self):
        """小跳：轻点上方向，低轨道快速落地"""
        if self.on_ground:
            self._jump_type = "hop"
            self.vel_y = HOP_VEL_Y
            self.on_ground = False

    def start_super_jump(self):
        """超跳：↓→↑ 或跑动中起跳，更高更远"""
        if self.on_ground:
            self._jump_type = "super"
            self.vel_y = SUPER_JUMP_VEL_Y
            self.on_ground = False

    def start_dash(self):
        """前冲：→→ 快速前移"""
        if not self.on_ground:
            return
        self._dash_dir = 1
        self.dash_timer = DASH_DURATION
        self.vel_x = DASH_SPEED if self.facing_right else -DASH_SPEED
        self._jump_type = ""

    def start_backdash(self):
        """后撤步：←← 快速后退，前 N 帧无敌"""
        if not self.on_ground:
            return
        self._dash_dir = -1
        self.dash_timer = BACKDASH_DURATION
        self.vel_x = -DASH_SPEED if self.facing_right else DASH_SPEED
        self._jump_type = ""

    # ── 能量系统 ──

    @property
    def power_stocks(self) -> int:
        """当前持有的能量条数"""
        return self.power_gauge // METER_PER_STOCK

    @property
    def max_power(self) -> int:
        return METER_PER_STOCK * MAX_POWER_STOCKS

    def add_meter(self, amount: int):
        if self.max_mode:
            return  # MAX 模式下不涨气
        self.power_gauge = min(self.power_gauge + amount, self.max_power)

    def can_use_super(self, cost: int = METER_PER_STOCK) -> bool:
        return self.power_gauge >= cost

    def consume_meter(self, amount: int):
        self.power_gauge = max(0, self.power_gauge - amount)

    def activate_max(self) -> bool:
        """发动 MAX 模式：需要体力 ≤ 25% 且至少 1 条气"""
        if self.health > MAX_HEALTH * MAX_HEALTH_THRESHOLD:
            return False
        if self.power_gauge < METER_PER_STOCK:
            return False
        self.max_mode = True
        self.max_timer = MAX_MODE_DURATION
        self.power_gauge = 0
        return True

    def deactivate_max(self):
        self.max_mode = False
        self.max_timer = 0

    def start_special(self, move_name: str):
        """加载并发动必杀技/超必杀技。处理气量消耗。"""
        try:
            move = load_move(move_name)
        except FileNotFoundError:
            return
        # 超必杀技需要消耗气
        if move.meter_cost > 0:
            if not self.can_use_super(move.meter_cost):
                return
            self.consume_meter(move.meter_cost)
        # 发动招式后获得微量气
        if move.move_type == "special":
            self.add_meter(METER_GAIN_SPECIAL)
        self.start_move(move)

    # 近身判定距离
    PROXIMITY_THRESHOLD = 80

    def attack(self, button: str = "a"):
        """按按钮触发普攻。button: 'a'/'b'/'c'/'d'"""
        move = self._get_normal_move(button)
        if move is not None:
            self.start_move(move)

    def _get_normal_move(self, button: str):
        """根据当前状态选择普攻：蹲姿→crouch_X, 空中→jump_X, 站立→stand_X"""
        if self.is_crouching:
            prefix = "crouch"
        elif not self.on_ground:
            prefix = "jump"
        else:
            prefix = "stand"
        # 优先加载状态特定招式，失败回退到站姿，再失败用默认
        try:
            return load_move(f"{prefix}_{button}")
        except FileNotFoundError:
            pass
        try:
            return load_move(f"stand_{button}")
        except FileNotFoundError:
            return DEFAULT_MOVE

    def start_move(self, move: MoveData):
        if self.attack_cooldown > 0:
            return
        if self.current_move is not None:
            if not self.fsm.can_cancel_into(self, move.name):
                return
        elif not self.is_actionable() and not self.fsm.can_cancel_into(self, move.name):
            return
        # dash cancel: 中断 dash/backdash
        if self.dash_timer > 0:
            self.dash_timer = 0
            self._dash_dir = 0
            self.vel_x = 0.0
        self.current_move = move
        self.move_frame = 0
        self.attack_cooldown = ATTACK_COOLDOWN
        self.connected_hit_ids.clear()
        self.animator.play("attack")

    def take_damage(self, amount: int, hitstun: int = 0,
                    knockback_x: float = 0.0, knockback_y: float = 0.0,
                    hitstop: int = 0):
        if self.dead:
            return
        # MAX 模式防御加成
        if self.max_mode:
            amount = max(1, int(amount * MAX_MODE_DEFENSE_MULT))
        self.health = max(0, self.health - amount)
        self.hit_flash = HIT_FLASH_FRAMES
        self.hitstun = hitstun
        self.hitstop = hitstop
        self.knockback_vel = knockback_x
        self.vel_y = knockback_y
        # 受击涨气
        self.add_meter(METER_GAIN_GOT_HIT)
        if self.health == 0:
            self.dead = True

    # ── 防御系统 ──

    def is_actionable(self) -> bool:
        """是否可行动（不在任何硬直中）"""
        return self.fsm.can_act()

    def check_blocking(self, attacker_x: float,
                       holding_left: bool, holding_right: bool,
                       holding_down: bool = False):
        """每帧在碰撞检测前调用，更新防御 / 蹲姿 / 蹲防姿态"""
        # 重置
        self.is_blocking = False
        self.is_crouch_blocking = False
        self.is_crouching = False

        if not self.on_ground:
            return
        if self.blockstun > 0:
            return
        if self.guard_broken:
            return
        # dash/backdash 中不可防御
        if self.dash_timer > 0:
            return

        holding_back = False
        if attacker_x > self.x and holding_left:
            holding_back = True
        elif attacker_x < self.x and holding_right:
            holding_back = True

        if holding_down:
            if holding_back:
                self.is_crouch_blocking = True
            else:
                self.is_crouching = True
        elif holding_back:
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

    def try_tech(self, holding_dir: bool):
        """受身：hitstun 最后 TECH_WINDOW 帧内按住方向键可提前恢复"""
        if self.fsm.can_tech(self, holding_dir):
            self.hitstun = max(0, self.hitstun - TECH_RECOVERY)

    # ── 每帧更新 ──

    def update(self):
        # hitstop 期间位置冻结，但计时器照常推进
        if self.hitstop > 0:
            self.hitstop -= 1
        else:
            self.apply_gravity()
            self.x += self.vel_x

            # 击退（摩擦力衰减 + 版边衰减）
            if abs(self.knockback_vel) > 0.01:
                # 版边击退衰减：防止无限连
                near_left = (self.x < KNOCKBACK_CORNER_MARGIN
                             and self.knockback_vel < 0)
                near_right = (self.x > SCREEN_W - FIGHTER_W - KNOCKBACK_CORNER_MARGIN
                              and self.knockback_vel > 0)
                if near_left or near_right:
                    self.knockback_vel *= KNOCKBACK_CORNER_FACTOR
                self.x += self.knockback_vel
                self.knockback_vel *= KNOCKBACK_FRICTION
            else:
                self.knockback_vel = 0.0

        self.clamp_to_screen()

        # 落地时清除 jump 类型标记
        if self.on_ground:
            self._jump_type = ""

        # dash / backdash 计时器
        if self.dash_timer > 0:
            self.dash_timer -= 1
            if self.dash_timer == 0:
                self._dash_dir = 0
                self.vel_x = 0.0

        # MAX 模式计时器
        if self.max_mode:
            self.max_timer -= 1
            if self.max_timer <= 0:
                self.deactivate_max()

        # 前进涨气（行走时每帧微量）
        if self._moving and self.on_ground and self.dash_timer == 0:
            if not self.is_blocking and not self.is_crouching:
                self.add_meter(1)  # 实际上是检查是否在向前走
                # KOF: forward walk gains meter, backward doesn't
                # Simplified: moving on ground gains meter

        # 移动检测（用于走路动画）
        self._moving = abs(self.x - self._prev_x) > 0.01
        self._prev_x = self.x

        # 递减计时器
        if self.current_move is not None:
            self.move_frame += 1
            if self.move_frame >= self.current_move.total_frames:
                self.current_move = None
                self.move_frame = 0
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.hitstun > 0:
            self.hitstun -= 1
        if self.blockstun > 0:
            self.blockstun -= 1
            if self.blockstun == 0 and self.guard_broken:
                self.guard_broken = False
                self.block_health = MAX_BLOCK_HEALTH

        # 同步动作状态机
        self.fsm.sync(self)

        # 推进动画
        self.animator.tick()

    # ── 绘制 ──

    def _anim_state(self) -> str:
        """根据 FSM 状态返回动画名"""
        if self.hit_flash > 0:
            return "hit"
        s = self.fsm.state
        if s == ActionState.ATTACK:
            return "attack"
        if s.is_stunned:
            return "hit"
        if s == ActionState.DASH:
            return "dash"
        if s == ActionState.BACKDASH:
            return "backdash"
        if s == ActionState.HOP:
            return "jump"
        if s == ActionState.SUPER_JUMP:
            return "jump"
        if s == ActionState.JUMP:
            return "jump"
        if s in (ActionState.BLOCK, ActionState.CROUCH_BLOCK):
            return "block"
        if s == ActionState.CROUCH:
            return "crouch"
        if s == ActionState.WALK:
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