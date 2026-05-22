"""必杀技指令识别引擎 — MotionInput 定义 + 检测逻辑"""

from dataclasses import dataclass, field
from typing import Optional
from input_system import Action, InputBuffer, DirectionBuffer

# ── 按钮组（用于接受 P=拳 / K=脚 等通用定义）──

P_BUTTONS = {Action.LIGHT_PUNCH, Action.HEAVY_PUNCH}
K_BUTTONS = {Action.LIGHT_KICK, Action.HEAVY_KICK}
ANY_BUTTON = P_BUTTONS | K_BUTTONS


@dataclass
class MotionInput:
    """一个必杀技指令定义"""
    name: str                    # 招式标识符，如 "qcf_p"
    motions: list                # 方向序列，如 [D, F]
    accept_buttons: set          # 可接受的按钮集合
    window: int = 15             # 方向输入有效窗口（帧）
    charge_time: int = 0         # >0 表示蓄力技（需按住首方向 N 帧）
    priority: int = 0            # 优先级（越高越优先）
    button_must_be: Optional[Action] = None  # 限定具体按钮（如仅 LP）


# ═══════════════════════════════════════════════
# 招式数据库
# ═══════════════════════════════════════════════

# 优先级：超必杀(30) > 必杀技(20) > 特殊技(10) > 普攻(0)

MOTION_DATABASE: list[MotionInput] = [
    # ── 必杀技 ──
    # 波动拳 ↓↘→ + P
    MotionInput("qcf_p", [Action.MOVE_DOWN, Action.MOVE_RIGHT],
                P_BUTTONS, window=15, priority=20),
    # 升龙拳 →↓↘ + P
    MotionInput("dp_p", [Action.MOVE_RIGHT, Action.MOVE_DOWN, Action.MOVE_RIGHT],
                P_BUTTONS, window=12, priority=20),
    # 波动脚 ↓↘→ + K
    MotionInput("qcf_k", [Action.MOVE_DOWN, Action.MOVE_RIGHT],
                K_BUTTONS, window=15, priority=20),
    # 龙卷旋风脚 ↓↙← + K
    MotionInput("qcb_k", [Action.MOVE_DOWN, Action.MOVE_LEFT],
                K_BUTTONS, window=15, priority=20),
    # 反波动拳 ←↙↓↘→ + P
    MotionInput("hcb_p", [Action.MOVE_LEFT, Action.MOVE_DOWN, Action.MOVE_RIGHT],
                P_BUTTONS, window=20, priority=20),

    # ── 超必杀技 ──
    # 超波动拳 ↓↘→↓↘→ + P（消耗 1 条气）
    MotionInput("qcf_qcf_p", [Action.MOVE_DOWN, Action.MOVE_RIGHT,
                Action.MOVE_DOWN, Action.MOVE_RIGHT],
                P_BUTTONS, window=30, priority=30),
    # 超升龙拳 ↓↘→↘↓↙← + P
    MotionInput("qcf_hcb_p", [Action.MOVE_DOWN, Action.MOVE_RIGHT,
                Action.MOVE_DOWN, Action.MOVE_LEFT],
                P_BUTTONS, window=30, priority=30),
]

# 按优先级降序排列
MOTION_DATABASE.sort(key=lambda m: m.priority, reverse=True)


# ═══════════════════════════════════════════════
# 检测函数
# ═══════════════════════════════════════════════

def check_special_move(
    input_buf: InputBuffer,
    dir_buf: DirectionBuffer,
    just_pressed_button: Optional[Action],
) -> Optional[str]:
    """
    在攻击按钮按下的帧调用，检测是否触发必杀技。
    返回招式名（如 "qcf_p"），未检测到返回 None。

    检测流程：
    1. 从 DirectionBuffer 取出方向序列
    2. 与 MOTION_DATABASE 逐一匹配
    3. 返回优先级最高的命中招式
    """
    if just_pressed_button is None:
        return None

    for motion in MOTION_DATABASE:
        # 按钮匹配
        if just_pressed_button not in motion.accept_buttons:
            continue
        if motion.button_must_be is not None and just_pressed_button != motion.button_must_be:
            continue

        # 方向序列匹配
        if motion.charge_time > 0:
            if dir_buf.check_charge(motion.motions[0], motion.charge_time):
                return motion.name
        else:
            if dir_buf.has_motion_sequence(motion.motions, motion.window):
                return motion.name

    return None


def get_motion_by_name(name: str) -> Optional[MotionInput]:
    for m in MOTION_DATABASE:
        if m.name == name:
            return m
    return None
