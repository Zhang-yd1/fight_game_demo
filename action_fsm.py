"""动作状态机 — ActionState 枚举 + ActionFSM 状态管理"""

from enum import Enum, auto


class ActionState(Enum):
    """战士当前动作状态（单一来源，替代散落的 bool 标志）"""
    IDLE = auto()          # 站立待机
    WALK = auto()          # 地面行走
    CROUCH = auto()        # 蹲姿
    JUMP = auto()          # 普跳
    HOP = auto()           # 小跳（轻点上）
    SUPER_JUMP = auto()    # 超跳（↓→↑ 或跑跳）
    DASH = auto()          # 前冲
    BACKDASH = auto()      # 后撤步
    DODGE = auto()         # 紧急回避（A+B）
    ATTACK = auto()        # 攻击中（startup / active / recovery）
    HITSTUN = auto()       # 受击硬直
    BLOCKSTUN = auto()     # 防御硬直
    BLOCK = auto()         # 主动站防（未受击）
    CROUCH_BLOCK = auto()  # 蹲防
    GUARD_BROKEN = auto()  # 破防大硬直
    DEAD = auto()          # 死亡

    # ── 状态组 ──

    @property
    def is_stunned(self) -> bool:
        """是否处于不可行动的硬直状态"""
        return self in (ActionState.HITSTUN, ActionState.BLOCKSTUN,
                        ActionState.GUARD_BROKEN)

    @property
    def is_grounded(self) -> bool:
        """是否可进行地面操作（含蹲姿和防御）"""
        return self in (ActionState.IDLE, ActionState.WALK,
                        ActionState.CROUCH,
                        ActionState.BLOCK, ActionState.CROUCH_BLOCK)

    @property
    def is_actionable(self) -> bool:
        """是否可以接受新的攻击/跳跃输入（不含防御姿态）"""
        return self in (ActionState.IDLE, ActionState.WALK,
                        ActionState.CROUCH)

    @property
    def is_airborne(self) -> bool:
        """是否在空中（跳跃/小跳/超跳）"""
        return self in (ActionState.JUMP, ActionState.HOP,
                        ActionState.SUPER_JUMP)


class ActionFSM:
    """管理 Fighter 动作状态及其转换规则"""

    def __init__(self):
        self.state = ActionState.IDLE
        self.prev_state = ActionState.IDLE

    def sync(self, fighter) -> ActionState:
        """每帧根据 Fighter 物理状态同步 FSM 状态"""
        new_state = self._derive(fighter)
        if new_state != self.state:
            self.prev_state = self.state
            self.state = new_state
        return self.state

    def _derive(self, f) -> ActionState:
        """从 Fighter 内部标志推导当前动作状态（优先级从高到低）"""
        if f.dead:
            return ActionState.DEAD
        if f.guard_broken:
            return ActionState.GUARD_BROKEN
        if f.blockstun > 0:
            return ActionState.BLOCKSTUN
        if f.hitstun > 0:
            return ActionState.HITSTUN
        if f.current_move is not None:
            return ActionState.ATTACK
        # dash/backdash/dodge are auto-movement states tracked by dash_timer
        if f.dash_timer > 0:
            if f._dash_dir < 0:
                return ActionState.BACKDASH
            return ActionState.DASH
        # airborne states (set by jump variants)
        if f._jump_type == "hop":
            return ActionState.HOP
        if f._jump_type == "super":
            return ActionState.SUPER_JUMP
        if not f.on_ground:
            return ActionState.JUMP
        if f.is_crouch_blocking:
            return ActionState.CROUCH_BLOCK
        if f.is_blocking:
            return ActionState.BLOCK
        if f.is_crouching:
            return ActionState.CROUCH
        if f._moving:
            return ActionState.WALK
        return ActionState.IDLE

    # ── 行动判定 ──

    def can_act(self) -> bool:
        """是否可以接受攻击 / 跳跃输入"""
        return self.state.is_actionable

    def can_move(self) -> bool:
        """是否可以地面移动（蹲姿/蹲防下不可移动）"""
        return self.state in (ActionState.IDLE, ActionState.WALK,
                              ActionState.BLOCK)

    def can_block(self) -> bool:
        """是否可以进入防御姿态"""
        return self.state in (ActionState.IDLE, ActionState.WALK,
                              ActionState.BLOCK, ActionState.JUMP,
                              ActionState.BLOCKSTUN)

    def can_dash_cancel(self) -> bool:
        """dash/backdash 中是否可以取消为攻击"""
        return self.state in (ActionState.DASH, ActionState.BACKDASH)

    def can_tech(self, fighter, holding_dir: bool) -> bool:
        """
        受身判定：hitstun 最后 TECH_WINDOW 帧内按住任意方向键
        可提前 2 帧恢复。
        """
        if self.state != ActionState.HITSTUN:
            return False
        if not holding_dir:
            return False
        return fighter.hitstun <= TECH_WINDOW

    # ── Cancel 判定 ──

    def can_cancel_into(self, fighter, move_name: str) -> bool:
        """
        当前帧是否可以将当前动作取消为目标招式。
        - ATTACK 状态：需在 cancel 窗口内且目标在 cancel_into 列表中
        - DASH/BACKDASH：可取消为任意攻击（dash cancel）
        """
        if self.state == ActionState.ATTACK:
            move = fighter.current_move
            if move is None:
                return False
            frame = fighter.move_frame
            win_start, win_end = move.cancel_window
            if win_start <= frame <= win_end:
                return move_name in move.cancel_into
            return False
        if self.state in (ActionState.DASH, ActionState.BACKDASH):
            return True
        return False


# ── 受身窗口 ──

TECH_WINDOW = 4  # hitstun 结束前 N 帧内可受身
TECH_RECOVERY = 2  # 受身成功后提前恢复的帧数
