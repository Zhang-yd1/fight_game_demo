"""格斗游戏 — 输入系统抽象（键位配置 + 动作映射 + 输入缓冲）"""

from collections import deque
from enum import Enum, auto
from typing import Optional, List, Tuple
import pygame


# ═══════════════════════════════════════════════
# 逻辑动作枚举（与物理按键解耦）
# ═══════════════════════════════════════════════

class Action(Enum):
    # ── 方向 ──
    MOVE_LEFT    = auto()
    MOVE_RIGHT   = auto()
    MOVE_UP      = auto()
    MOVE_DOWN    = auto()
    JUMP         = auto()       # 向后兼容别名
    # ── 4 攻击按钮 ──
    LIGHT_PUNCH  = auto()       # A — 轻拳
    LIGHT_KICK   = auto()       # B — 轻脚
    HEAVY_PUNCH  = auto()       # C — 重拳
    HEAVY_KICK   = auto()       # D — 重脚
    ATTACK       = auto()       # 向后兼容别名
    # ── 组合键（由 InputManager 自动检测）──
    DODGE         = auto()      # A+B 同时（紧急回避）
    CD_ATTACK     = auto()      # C+D 同时（吹飞攻击/防御取消）
    MAX_ACTIVATE  = auto()      # A+B+C 同时（MAX 发动）
    # ── 系统动作 ──
    PAUSE        = auto()
    CONFIRM      = auto()
    CANCEL       = auto()
    REMATCH      = auto()
    QUIT_TO_MENU = auto()


# ═══════════════════════════════════════════════
# 按键配置
# ═══════════════════════════════════════════════

class KeyConfig:
    """一套按键映射（可从 JSON 加载）"""

    def __init__(self, **kwargs):
        self._bindings: List[Tuple[int, Action]] = []
        for action_name, key_code in kwargs.items():
            action = Action[action_name]
            self._bindings.append((key_code, action))

    def key_for(self, action: Action) -> Optional[int]:
        for key, act in self._bindings:
            if act == action:
                return key
        return None

    def actions_for(self, key: int) -> List[Action]:
        return [act for k, act in self._bindings if k == key]

    def all_bindings(self) -> List[Tuple[int, Action]]:
        return list(self._bindings)


# ═══════════════════════════════════════════════
# 输入缓冲（连招检测基础）
# ═══════════════════════════════════════════════

class InputBuffer:
    """
    滚动输入缓冲，记录 (Action, 帧号) 序列。
    用于检测特定时间窗口内的动作序列（→ 必杀技判定）。
    """

    def __init__(self, max_size: int = 20, timeout: int = 60):
        self._buffer: deque = deque(maxlen=max_size)
        self._timeout = timeout
        self._frame = 0

    def tick(self):
        self._frame += 1

    def push(self, action: Action):
        self._buffer.append((action, self._frame))

    def has_sequence(self, actions: List[Action], window: int = 30) -> bool:
        """
        检查最近 window 帧内是否按顺序输入了指定动作序列。
        用于必杀技判定，如 [MOVE_DOWN, MOVE_DOWN_RIGHT, MOVE_RIGHT, ATTACK] → 波动拳。
        """
        if len(actions) > len(self._buffer):
            return False

        buf_list = list(self._buffer)
        ti = len(actions) - 1
        bi = len(buf_list) - 1

        while ti >= 0 and bi >= 0:
            act, frame = buf_list[bi]
            if self._frame - frame > window:
                return False
            if act == actions[ti]:
                ti -= 1
            bi -= 1

        return ti < 0

    def clear(self):
        self._buffer.clear()


# ═══════════════════════════════════════════════
# 输入管理器
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
# 方向输入缓冲（Dash / Super Jump 检测）
# ═══════════════════════════════════════════════

DIRECTIONS = {Action.MOVE_LEFT, Action.MOVE_RIGHT, Action.MOVE_UP, Action.MOVE_DOWN}


class DirectionBuffer:
    """记录方向键序列，用于检测 →→ / ←← / ↓→↑ 等移动指令"""

    def __init__(self, max_size: int = 30):
        self._buffer: deque[tuple[Action, int]] = deque(maxlen=max_size)
        self._frame = 0

    def tick(self):
        self._frame += 1

    def push(self, action: Action):
        if action in DIRECTIONS:
            self._buffer.append((action, self._frame))

    def check_dash(self) -> int | None:
        """
        检测 →→ 或 ←← 在 dash 输入窗口内。
        返回 1（前冲）、-1（后撤步），未检测到返回 None。
        """
        window = self._frame - DASH_INPUT_WINDOW
        recent = [(a, f) for a, f in self._buffer if f >= window]
        if len(recent) < 2:
            return None
        # 找最近两次同方向按下（必须是两次独立的按下）
        last = recent[-1]
        for i in range(len(recent) - 2, -1, -1):
            if recent[i][0] == last[0]:
                # 两次同方向在窗口内
                if last[0] == Action.MOVE_RIGHT:
                    return 1
                if last[0] == Action.MOVE_LEFT:
                    return -1
        return None

    def check_super_jump(self) -> bool:
        """检测 ↓→↑ 序列（super jump 指令）"""
        return self.has_motion_sequence(
            [Action.MOVE_DOWN, Action.MOVE_RIGHT, Action.MOVE_UP],
            DASH_INPUT_WINDOW,
        )

    def has_motion_sequence(self, motions: list, window: int) -> bool:
        """
        检测方向序列是否在 window 帧内按顺序出现。
        用于必杀技指令识别，如 [D, F] → qcf。
        序列中的方向不需要连续，中间可以有其他方向。
        """
        if len(motions) == 0:
            return False
        w = self._frame - window
        recent = [(a, f) for a, f in self._buffer if f >= w]
        ti = len(motions) - 1
        for a, _ in reversed(recent):
            if a == motions[ti]:
                ti -= 1
                if ti < 0:
                    return True
        return False

    def check_charge(self, direction: Action, required_frames: int) -> bool:
        """
        检测蓄力指令：direction 是否被连续按住至少 required_frames 帧。
        用于蓄力技如 [B]→F+P（sonic boom 类）。
        """
        if len(self._buffer) == 0:
            return False
        last_dir = self._buffer[-1][0]
        if last_dir != direction:
            return False
        # 统计连续持有的帧数
        count = 0
        for a, f in reversed(self._buffer):
            if a == direction:
                count += 1
            else:
                break
        # 每帧是一次按键事件，实际按住持续帧需要从时间判断
        # 简化：从第一次出现该方向到当前帧的时间跨度
        first = None
        for a, f in self._buffer:
            if a == direction:
                first = f
            else:
                first = None
        if first is None:
            return False
        return (self._frame - first) >= required_frames

    def clear(self):
        self._buffer.clear()


# dash input window imported from config at module level — set after config loads
DASH_INPUT_WINDOW = 20


# ═══════════════════════════════════════════════
# 输入管理器
# ═══════════════════════════════════════════════

class InputManager:
    """
    单个玩家 / 控制器的输入管理器。
    每帧调用 update() 更新按键状态，提供 is_held / just_pressed 查询。
    """

    def __init__(self, key_config: KeyConfig):
        self.config = key_config
        self.buffer = InputBuffer()
        self.dir_buffer = DirectionBuffer()
        self._prev: set[int] = set()
        self._curr: set[int] = set()
        self._frame_count = 0
        # 上方向按住/松开帧号（用于 hop 判定）
        self._up_press_frame = -1
        self._up_release_frame = -1

    def update(self):
        """每帧最先调用，轮询键盘状态并更新缓冲"""
        self._prev = self._curr
        self._curr = set()
        self._frame_count += 1
        self.buffer.tick()
        self.dir_buffer.tick()

        pressed = pygame.key.get_pressed()
        for key, action in self.config.all_bindings():
            if pressed[key]:
                self._curr.add(key)
                if key not in self._prev:
                    self.buffer.push(action)
                    self.dir_buffer.push(action)

        # ── 上方向按住/松开追踪 ──
        if self.just_pressed(Action.MOVE_UP):
            self._up_press_frame = self._frame_count
        if self.just_released(Action.MOVE_UP):
            self._up_release_frame = self._frame_count

        # ── 组合键检测（A+B / C+D）──
        a_held = self.is_held(Action.LIGHT_PUNCH)
        b_held = self.is_held(Action.LIGHT_KICK)
        c_held = self.is_held(Action.HEAVY_PUNCH)
        d_held = self.is_held(Action.HEAVY_KICK)

        # A+B → DODGE（本帧首次同时按下任一按钮时触发）
        if a_held and b_held:
            if self.just_pressed(Action.LIGHT_PUNCH) or self.just_pressed(Action.LIGHT_KICK):
                self.buffer.push(Action.DODGE)

        # C+D → CD_ATTACK
        if c_held and d_held:
            if self.just_pressed(Action.HEAVY_PUNCH) or self.just_pressed(Action.HEAVY_KICK):
                self.buffer.push(Action.CD_ATTACK)

        # A+B+C → MAX_ACTIVATE
        if a_held and b_held and c_held:
            if self.just_pressed(Action.HEAVY_PUNCH):
                self.buffer.push(Action.MAX_ACTIVATE)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def up_held_frames(self) -> int:
        """
        MOVE_UP 松开的持续帧数（用于 hop vs jump 判定）。
        如果当前正在按住，返回当前已按住的帧数。
        """
        if self.is_held(Action.MOVE_UP):
            return self._frame_count - self._up_press_frame
        if self._up_release_frame > 0 and self._up_press_frame > 0:
            return self._up_release_frame - self._up_press_frame
        return 0

    def is_held(self, action: Action) -> bool:
        """动作对应按键是否正在被按住"""
        for key, act in self.config.all_bindings():
            if act == action and key in self._curr:
                return True
        return False

    def just_pressed(self, action: Action) -> bool:
        """动作对应按键是否在本帧首次按下（边沿触发）"""
        for key, act in self.config.all_bindings():
            if act == action and key in self._curr and key not in self._prev:
                return True
        return False

    def any_just_pressed(self, *actions: Action) -> Optional[Action]:
        """多个动作中第一个本帧按下的，未按下返回 None"""
        for action in actions:
            if self.just_pressed(action):
                return action
        return None

    def just_released(self, action: Action) -> bool:
        """动作对应按键是否在本帧刚松开（负边沿触发）"""
        for key, act in self.config.all_bindings():
            if act == action and key in self._prev and key not in self._curr:
                return True
        return False