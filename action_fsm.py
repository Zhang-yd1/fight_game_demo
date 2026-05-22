"""动作状态机 — ActionState 枚举 + ActionFSM 状态管理"""

from enum import Enum, auto


class ActionState(Enum):
    """战士当前动作状态（单一来源，替代散落的 bool 标志）"""
    IDLE = auto()          # 站立待机
    WALK = auto()          # 地面行走
    JUMP = auto()          # 空中
    ATTACK = auto()        # 攻击中（startup / active / recovery）
    HITSTUN = auto()       # 受击硬直
    BLOCKSTUN = auto()     # 防御硬直
    BLOCK = auto()         # 主动防御（未受击）
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
        """是否可进行地面操作"""
        return self in (ActionState.IDLE, ActionState.WALK,
                        ActionState.BLOCK)

    @property
    def is_actionable(self) -> bool:
        """是否可以接受新的行动输入"""
        return self in (ActionState.IDLE, ActionState.WALK)


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
        if not f.on_ground:
            return ActionState.JUMP
        if f.is_blocking:
            return ActionState.BLOCK
        if f._moving:
            return ActionState.WALK
        return ActionState.IDLE

    # ── 行动判定 ──

    def can_act(self) -> bool:
        """是否可以接受移动 / 攻击输入"""
        return self.state.is_actionable

    def can_block(self) -> bool:
        """是否可以进入防御姿态"""
        return self.state in (ActionState.IDLE, ActionState.WALK,
                              ActionState.BLOCK, ActionState.JUMP,
                              ActionState.BLOCKSTUN)

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
        需要当前招式在 cancel 窗口内 且 目标在 cancel_into 列表中。
        """
        if self.state != ActionState.ATTACK:
            return False
        move = fighter.current_move
        if move is None:
            return False
        frame = fighter.move_frame
        win_start, win_end = move.cancel_window
        if win_start <= frame <= win_end:
            return move_name in move.cancel_into
        return False


# ── 受身窗口 ──

TECH_WINDOW = 4  # hitstun 结束前 N 帧内可受身
TECH_RECOVERY = 2  # 受身成功后提前恢复的帧数
