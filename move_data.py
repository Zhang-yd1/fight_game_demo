"""帧数据系统 — MoveData 定义 + JSON 加载"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from collision import CollisionBox


@dataclass
class MovePhase:
    """单个阶段：startup / active / recovery"""
    stage: str           # "startup" | "active" | "recovery"
    duration: int
    hitboxes: list = field(default_factory=list)
    hurtboxes: list = field(default_factory=list)
    invincible: bool = False  # 帧级无敌（如升龙拳 startup）

    @classmethod
    def from_dict(cls, d: dict) -> 'MovePhase':
        hitboxes = [_box_from_dict(b, "hit") for b in d.get("hitboxes", [])]
        hurtboxes = [_box_from_dict(b, "hurt") for b in d.get("hurtboxes", [])]
        return cls(
            stage=d["stage"],
            duration=d["duration"],
            hitboxes=hitboxes,
            hurtboxes=hurtboxes,
            invincible=d.get("invincible", False),
        )


@dataclass
class MoveData:
    """一个招式 / 必杀技的完整帧数据"""
    name: str
    startup: int
    active: int
    recovery: int
    phases: list[MovePhase]
    cancel_into: list = field(default_factory=list)
    cancel_window: tuple = (0, 0)
    on_hit: int = 0
    on_block: int = 0
    # 新增字段
    move_type: str = "normal"   # "normal" | "special" | "super" | "command_normal" | "throw"
    motion_input: str = ""      # 指令标识符，如 "qcf_p"
    meter_gain: int = 0         # 命中后获得的气量
    meter_cost: int = 0         # 消耗气量（超必杀）

    @property
    def total_frames(self) -> int:
        return self.startup + self.active + self.recovery

    def get_phase(self, frame: int) -> Optional[MovePhase]:
        """返回第 frame 帧（0-indexed）所属的阶段"""
        if frame < 0 or frame >= self.total_frames:
            return None
        elapsed = 0
        for phase in self.phases:
            if frame < elapsed + phase.duration:
                return phase
            elapsed += phase.duration
        return None

    def is_active(self, frame: int) -> bool:
        phase = self.get_phase(frame)
        return phase is not None and phase.stage == "active"

    @classmethod
    def from_json(cls, path: str) -> 'MoveData':
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        phases = [MovePhase.from_dict(p) for p in d["frames"]]
        cancel_win = tuple(d.get("cancel_window", [0, 0]))
        return cls(
            name=d["name"],
            startup=d["startup"],
            active=d["active"],
            recovery=d["recovery"],
            phases=phases,
            cancel_into=d.get("cancel_into", []),
            cancel_window=cancel_win,
            on_hit=d.get("on_hit", 0),
            on_block=d.get("on_block", 0),
            move_type=d.get("type", "normal"),
            motion_input=d.get("input", ""),
            meter_gain=d.get("meter_gain", 0),
            meter_cost=d.get("meter_cost", 0),
        )


def _box_from_dict(d: dict, default_type: str) -> CollisionBox:
    return CollisionBox(
        offset_x=d.get("offset_x", d.get("x", 0)),
        offset_y=d.get("offset_y", d.get("y", 0)),
        width=d.get("width", d.get("w", 0)),
        height=d.get("height", d.get("h", 0)),
        type=d.get("type", default_type),
        damage=d.get("damage", 0),
        knockback_x=d.get("knockback_x", d.get("kb_x", 0.0)),
        knockback_y=d.get("knockback_y", d.get("kb_y", 0.0)),
        hitstun=d.get("hitstun", 0),
        blockstun=d.get("blockstun", 0),
        hitstop=d.get("hitstop", 0),
        chip_damage=d.get("chip_damage", 0),
        attacker_hitstop=d.get("attacker_hitstop", 0),
        hit_id=d.get("hit_id", 0),
    )


# ── 预加载默认招式 ──

_move_dir = os.path.join(os.path.dirname(__file__), 'data', 'moves')

def load_move(name: str) -> MoveData:
    """按名称加载招式 JSON"""
    path = os.path.join(_move_dir, f'{name}.json')
    if not os.path.exists(path):
        raise FileNotFoundError(f"Move file not found: {path}")
    return MoveData.from_json(path)


# 默认普攻（模块加载时构建，避免重复 IO）
try:
    DEFAULT_MOVE = load_move('stand_a')
except FileNotFoundError:
    DEFAULT_MOVE = None
