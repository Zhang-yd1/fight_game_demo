"""格斗游戏 — 输入系统抽象（键位配置 + 动作映射 + 输入缓冲）"""

from collections import deque
from enum import Enum, auto
from typing import Optional, List, Tuple
import pygame


# ═══════════════════════════════════════════════
# 逻辑动作枚举（与物理按键解耦）
# ═══════════════════════════════════════════════

class Action(Enum):
    # 战斗动作
    MOVE_LEFT    = auto()
    MOVE_RIGHT   = auto()
    JUMP         = auto()
    ATTACK       = auto()
    # 系统动作
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

class InputManager:
    """
    单个玩家 / 控制器的输入管理器。
    每帧调用 update() 更新按键状态，提供 is_held / just_pressed 查询。
    """

    def __init__(self, key_config: KeyConfig):
        self.config = key_config
        self.buffer = InputBuffer()
        self._prev: set[int] = set()
        self._curr: set[int] = set()

    def update(self):
        """每帧最先调用，轮询键盘状态并更新缓冲"""
        self._prev = self._curr
        self._curr = set()
        self.buffer.tick()

        pressed = pygame.key.get_pressed()
        for key, action in self.config.all_bindings():
            if pressed[key]:
                self._curr.add(key)
                if key not in self._prev:
                    self.buffer.push(action)

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