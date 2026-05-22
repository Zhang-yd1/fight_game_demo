# 拳皇风格格斗游戏 — 完整重构方案

## 目标定位

将当前原型重构为接近 KOF'96-'98 风格的 2D 格斗游戏。核心体验：
- 4 键操作（A/B/C/D = 轻拳/轻脚/重拳/重脚）
- 3v3 组队对战
- 丰富的移动系统（跑动/后撤步/小跳/大跳/超跳/蹲姿）
- 指令必杀技 + 超必杀技
- 能量槽 + MAX 模式
- 投技 + 拆投
- 紧急回避 + 防御取消

---

## 当前已完成（Phase 1 战斗核心）

| 模块 | 状态 |
|------|------|
| Hitbox/Hurtbox 分离 | 完成 — `collision.py` + `CollisionBox` |
| 防御系统 | 完成 — 站防/削血/破防/防御硬直 |
| 硬直系统 | 完成 — hitstun/hitstop/knockback |
| 击退系统 | 完成 — 摩擦力衰减/版边衰减 |
| 帧数据驱动 | 完成 — JSON + MoveData/MovePhase |
| 动作状态机 | 完成 — ActionFSM (9 状态) + 受身 + cancel 窗口 |

---

## Phase 2 — 4 键系统 + 蹲姿

### 2.1 Action 枚举扩展

将单一 `ATTACK` 拆分为 4 个攻击按键 + 方向扩展：

```python
class Action(Enum):
    # ── 方向 ──
    MOVE_LEFT    = auto()
    MOVE_RIGHT   = auto()
    MOVE_UP      = auto()
    MOVE_DOWN    = auto()
    JUMP         = auto()       # 上方向（保留向后兼容，实际 = MOVE_UP）
    # ── 4 攻击按钮 ──
    LIGHT_PUNCH  = auto()       # A — 轻拳
    LIGHT_KICK   = auto()       # B — 轻脚
    HEAVY_PUNCH  = auto()       # C — 重拳
    HEAVY_KICK   = auto()       # D — 重脚
    # ── 组合 ──
    DODGE         = auto()      # A+B 同时（紧急回避）
    CD_ATTACK     = auto()      # C+D 同时（吹飞攻击/防御取消）
    # ── 系统 ──
    PAUSE         = auto()
    CONFIRM       = auto()
    CANCEL        = auto()
    REMATCH       = auto()
    QUIT_TO_MENU  = auto()
```

### 2.2 键位配置更新

```json
// data/config.json — keybinds 部分
"keybinds": {
    "player1": {
        "move_left":   "a",
        "move_right":  "d",
        "move_up":     "w",
        "move_down":   "s",
        "light_punch": "j",       // A
        "light_kick":  "k",       // B
        "heavy_punch": "u",       // C
        "heavy_kick":  "i",       // D
        "pause":       "escape",
        ...
    }
}
```

**注意**：`dodge`（A+B）和 `cd_attack`（C+D）不需要单独绑定，由 `InputManager` 在 `update()` 中检测同时按下自动生成。

### 2.3 组合键检测

```python
# InputManager.update() 新增逻辑
def update(self):
    # ... 常规按键检测 ...
    
    # 组合键检测
    a_held = self.is_held(Action.LIGHT_PUNCH)
    b_held = self.is_held(Action.LIGHT_KICK)
    c_held = self.is_held(Action.HEAVY_PUNCH)
    d_held = self.is_held(Action.HEAVY_KICK)
    
    # A+B → DODGE（本帧首次同时按下）
    if a_held and b_held:
        if self.just_pressed(Action.LIGHT_PUNCH) or self.just_pressed(Action.LIGHT_KICK):
            self.buffer.push(Action.DODGE)
    
    # C+D → CD_ATTACK
    if c_held and d_held:
        if self.just_pressed(Action.HEAVY_PUNCH) or self.just_pressed(Action.HEAVY_KICK):
            self.buffer.push(Action.CD_ATTACK)
```

### 2.4 蹲姿系统

```python
# ActionState 新增
CROUCH = auto()       # 蹲姿
CROUCH_BLOCK = auto() # 蹲防

# Fighter 新增
self.is_crouching = False   # 按住 ↓ 且在 地面上
self.crouch_offset = 0      # 蹲姿时 hurtbox 高度缩减
```

```python
# Fighter.check_blocking() 扩展
def check_blocking(self, attacker_x, holding_left, holding_right, holding_down):
    # ... 
    if holding_down and self.on_ground:
        if holding_back:
            self.is_crouch_blocking = True  # 蹲防
        else:
            self.is_crouching = True  # 蹲姿（无防御）
```

**蹲姿特性**：
- 角色高度缩减（Hurtbox 缩小）
- 只能使用蹲姿普攻
- 对中段技无防御效果（蹲防不可防中段）
- 对下段技必须蹲防

**FSM 状态更新**：
```
IDLE / WALK + ↓ → CROUCH
CROUCH + 后退 → CROUCH_BLOCK
```

### 2.5 近距离/远距离普攻判定

同一按键根据与对手距离产生不同招式：

```python
# Fighter 新增
PROXIMITY_THRESHOLD = 80  # 近身判定距离（像素）

def _get_normal_move(self, button: str) -> MoveData:
    """根据距离和状态选择普攻"""
    dist = abs(self.x - opponent.x)
    if self.is_crouching:
        prefix = "crouch"
    elif not self.on_ground:
        prefix = "jump"
    elif dist < PROXIMITY_THRESHOLD:
        prefix = "close"
    else:
        prefix = "far"
    return load_move(f"{self.char_id}/{prefix}_{button}")
```

帧数据目录结构：
```
data/moves/kyo/
    far_a.json, far_b.json, far_c.json, far_d.json
    close_a.json, close_c.json, close_d.json
    crouch_a.json, crouch_b.json, crouch_c.json, crouch_d.json
    jump_a.json, jump_b.json, jump_c.json, jump_d.json
    qcf_p.json    # 百式·鬼烧
    dp_p.json     # 百八式·暗拂
    ...
```

---

## Phase 3 — 移动系统扩展

### 3.1 ActionFSM 扩展

```python
class ActionState(Enum):
    # 现有
    IDLE = auto()
    WALK = auto()
    JUMP = auto()
    ATTACK = auto()
    HITSTUN = auto()
    BLOCKSTUN = auto()
    BLOCK = auto()
    GUARD_BROKEN = auto()
    DEAD = auto()
    # 新增
    CROUCH = auto()          # 蹲姿
    CROUCH_BLOCK = auto()    # 蹲防
    DASH = auto()            # 前冲/跑动
    BACKDASH = auto()        # 后撤步
    HOP = auto()             # 小跳
    SUPER_JUMP = auto()      # 超跳
    DODGE = auto()           # 紧急回避
```

### 3.2 前冲 / 跑动（Dash / Run）

- 输入：→→（20 帧窗口内连续两次同方向）
- 前冲：快速向前移动一段固定距离，期间不可防御但可取消为攻击
- 跑动（按住 → 不放）：前冲后持续按住前方向进入跑动状态
- 跑动中可跳跃（跑跳）→ 更远的跳跃弧线

```python
class Fighter:
    dash_speed = 7.0
    dash_duration = 18       # 前冲总帧数
    dash_frame = 0
    backdash_invuln = 8      # 后撤步无敌帧
    
    def start_dash(self):
        self.fsm.state = ActionState.DASH
        self.dash_frame = 0
        self.vel_x = self.dash_speed * self.facing_direction
    
    def start_backdash(self):
        self.fsm.state = ActionState.BACKDASH
        self.dash_frame = 0
        self.vel_x = -self.dash_speed * self.facing_direction
```

### 3.3 跳跃变体

| 类型 | 输入 | 帧数（上升/下降） | 特性 |
|------|------|-------------------|------|
| 小跳（Hop） | 轻点上方向（≤4f） | 上升 10f | 低轨道，快速落地 |
| 普跳（Jump） | 按住上方向（>4f） | 上升 18f | 标准跳跃 |
| 超跳（Super Jump）| ↓ → ↑ 或 跑动中跳 | 上升 22f | 更高更远，可用空中必杀技 |
| 跑跳（Run Jump）| 跑动中按跳 | 上升 18f | 水平速度继承 |

```python
# InputManager 需要追踪上方向按住帧数
def update(self):
    # ...
    if self.just_pressed(Action.MOVE_UP):
        self._up_press_frame = self._frame_count
    if not self.is_held(Action.MOVE_UP):
        self._up_release_frame = self._frame_count

# Fighter.jump() 根据按住时长决定跳类型
def jump(self):
    held_frames = input_mgr.up_held_duration()
    if held_frames <= 4:
        self.start_hop()
    else:
        self.start_normal_jump()
```

### 3.4 方向输入缓冲

```python
class DirectionBuffer:
    """专门记录方向键序列，用于检测 →→ / ←← / ↓→↑ 等"""
    _buffer: deque  # (direction, frame)
    
    def check_dash(self) -> bool:
        """检测 →→ 或 ←←"""
    
    def check_super_jump(self) -> bool:
        """检测 ↓→↑ 序列"""
```

---

## Phase 4 — 必杀技系统

### 4.1 指令识别引擎

```python
@dataclass
class MotionInput:
    """一个必杀技指令定义"""
    name: str
    motions: list[Action]    # 方向序列，如 [↓, ↘, →]
    button: Action           # 触发按钮
    window: int = 15         # 方向输入有效窗口（帧）
    charge_time: int = 0     # > 0 表示蓄力技（需按住方向 N 帧）
    accept_buttons: list = None  # 可接受的按钮列表（如 P = A/C）

MOTION_DATABASE = {
    "qcf_p": MotionInput("qcf_p", [D, DF, F], P_BUTTON, window=15),
    "qcf_k": MotionInput("qcf_k", [D, DF, F], K_BUTTON, window=15),
    "dp_p":  MotionInput("dp_p",  [F, D, DF], P_BUTTON, window=12),
    "hcb_p": MotionInput("hcb_p", [F, DF, D, DB, B], P_BUTTON, window=20),
    # 蓄力技
    "sonic_boom": MotionInput("sonic_boom", [B, F], P_BUTTON, charge_time=40),
}
```

### 4.2 指令检测流程

```python
def check_special_move(fighter, input_buf, direction_buf) -> Optional[str]:
    """
    每帧在 Fighter.update() 前调用。
    1. 从 InputBuffer 取出最近的 (Direction, Attack) 序列
    2. 与 MOTION_DATABASE 逐一匹配
    3. 返回命中的招式名（取优先级最高者）
    """
    for move_name, motion in PRIORITY_ORDERED_MOTIONS:
        if motion.charge_time > 0:
            if direction_buf.check_charge(motion.motions[0], motion.charge_time):
                if input_buf.has_recent(motion.button, window=10):
                    return move_name
        else:
            if input_buf.has_motion_sequence(motion.motions, motion.button, motion.window):
                return move_name
    return None
```

**优先级规则**：
1. 超必杀技 > 必杀技 > 特殊技 > 普攻
2. 复杂指令 > 简单指令（如 DP → ↓↘→ > ↓↘→）
3. 重攻击 > 轻攻击（同指令不同按钮）

### 4.3 必杀技帧数据扩展

```json
// data/moves/kyo/qcf_p.json
{
    "name": "百八式·暗拂",
    "type": "special",
    "input": "qcf_p",
    "startup": 12,
    "active": 8,
    "recovery": 18,
    "meter_gain": 8,
    "frames": [
        {
            "stage": "startup",
            "duration": 12,
            "hitboxes": [],
            "hurtboxes": [...],
            "invincible": false
        },
        {
            "stage": "active",
            "duration": 8,
            "hitboxes": [
                {
                    "offset_x": 60, "offset_y": 10,
                    "width": 50, "height": 40,
                    "type": "projectile",
                    "damage": 65,
                    "knockback_x": 5.0, "knockback_y": -3.0,
                    "hitstun": 22, "blockstun": 14, "hitstop": 12,
                    "chip_damage": 10
                }
            ],
            "hurtboxes": [...]
        },
        {
            "stage": "recovery",
            "duration": 18,
            ...
        }
    ],
    "cancel_into": ["qcf_qcf_p"],
    "cancel_window": [12, 20],
    "on_hit": 2,
    "on_block": -8
}
```

新增字段：
- `type`: `"normal"` | `"special"` | `"super"` | `"command_normal"` | `"throw"`
- `input`: 指令标识符
- `meter_gain`: 命中后获得的气量
- `meter_cost`: 消耗气量（超必杀）
- `invincible`: 帧级无敌标记（用于升龙拳等）

---

## Phase 5 — 能量系统

### 5.1 能量槽设计（参考 KOF'97-'98）

```
┌─────────────────────────────────────────┐
│ Power Gauge: 0～128（一个能量 = 128）   │
│ 最多存储 3 个能量（Extra 模式 1 个）    │
│ 命中对手：+8                            │
│ 被对手命中：+10                         │
│ 防御对手攻击：+5                        │
│ 使用必杀技：+4                          │
│ 前进：微量 +1/frame                     │
└─────────────────────────────────────────┘
```

```python
class Fighter:
    power_gauge: int = 0        # 0～384（最多 3 条气，每条 128）
    max_power_stocks: int = 3
    max_mode: bool = False      # 是否处于 MAX 状态

    def add_meter(self, amount: int):
        self.power_gauge = min(
            self.power_gauge + amount,
            self.max_power_stocks * METER_PER_STOCK
        )
    
    def can_use_super(self, cost: int = 128) -> bool:
        return self.power_gauge >= cost
    
    def consume_meter(self, amount: int):
        self.power_gauge = max(0, self.power_gauge - amount)
```

### 5.2 MAX 发动

- 条件：体力 ≤ 25% 且 至少 1 条气
- 输入：A+B+C 同时按（自定义按键）
- 效果：进入 MAX 状态 ~10 秒，期间
  - 攻击力 × 1.25
  - 防御力 × 1.1
  - 可使用 MAX 超必杀技（消耗 2 条气）
  - 可使用 MAX2（隐藏超必杀，消耗 3 条气）
- 结束后恢复正常，气槽归零

```python
def activate_max(self):
    if self.health > MAX_HEALTH * 0.25:
        return False
    if self.power_gauge < METER_PER_STOCK:
        return False
    self.max_mode = True
    self.max_timer = MAX_MODE_DURATION  # ~600 帧（10秒）
    self.power_gauge = 0
    return True
```

### 5.3 HUD 显示

```
┌──────────────────────────────────────────────┐
│ [P1 HP ▌▌▌▌▌▌▌▌▌          ] [●][●][ ] │ P2 │
│ [P2 HP ▌▌▌▌▌▌           ] [●][ ][ ]        │
│                   TIMER 60                     │
└──────────────────────────────────────────────┘
```

---

## Phase 6 — 投技系统

### 6.1 普投

- 条件：地面、近身距离（≤ 60px）、对手可被投（非硬直/非空中）
- 输入：→/← + C 或 →/← + D（方向决定投的方向）
- 发生：1f（即时）
- 伤害：C 投 ~80, D 投 ~100
- 投空：播放失败动画（~20f 硬直）

```python
class Fighter:
    throw_range = 60
    
    def try_throw(self, opponent, direction, button):
        if abs(self.x - opponent.x) > self.throw_range:
            return self.start_throw_whiff(button)
        if not opponent.is_throwable():
            return
        move = load_move(f"{self.char_id}/throw_{button}")
        self.start_move(move)
        opponent.on_thrown(move)
```

### 6.2 拆投

被投方在被投发生帧（1f 判定）内输入 →/← + C/D 可拆投：

```python
TECH_THROW_WINDOW = 8  # 拆投窗口（帧）

def check_throw_tech(defender, attacker):
    if defender.fsm.state == ActionState.THROWN:
        if defender.throw_tech_frame <= TECH_THROW_WINDOW:
            if defender.is_pressing_throw_input():
                # 拆投成功，双方弹开
                defender.fsm.state = ActionState.IDLE
                attacker.fsm.state = ActionState.IDLE
                defender.apply_knockback(tech_throw_distance)
                attacker.apply_knockback(tech_throw_distance)
```

### 6.3 指令投

必杀技类型的投技（如大门的岚之山、克拉克的超级阿根廷攻击）：

```json
{
    "name": "岚之山",
    "type": "command_throw",
    "input": "hcb_f_p",
    "startup": 4,
    "range": 80,
    "damage": 180,
    "throw_invincible": false,
    "techable": true
}
```

指令投特性：
- 不可防御
- 不可拆投（或拆投窗口极短）
- 发生较慢（4-8f）
- 失败有较大硬直

---

## Phase 7 — 防御系统扩展

### 7.1 防御姿态完善

| 防御类型 | 输入 | 可防 | 不可防 |
|----------|------|------|--------|
| 站防 | 后退（站立） | 上段/中段/空中 | 下段 |
| 蹲防 | ↙（蹲下+后退） | 上段/下段 | 中段/空中 |
| 空防 | 不可 | - | - |

KOF 系列传统上**没有空中防御**，这是与街霸的重要区别。

```python
# 攻击属性标记
@dataclass
class CollisionBox:
    # ...
    attack_level: str = "mid"  # "high" | "mid" | "low" | "overhead" | "unblockable"
```

防御判定逻辑：
```python
def can_block_attack(self, hitbox: CollisionBox) -> bool:
    if self.fsm.state == ActionState.BLOCK:
        # 站防：不可防下段
        return hitbox.attack_level != "low"
    elif self.fsm.state == ActionState.CROUCH_BLOCK:
        # 蹲防：不可防中段
        return hitbox.attack_level not in ("mid", "overhead")
    return False
```

### 7.2 紧急回避（Dodge Roll）

- 输入：A+B（轻拳+轻脚同时）
- 效果：角色向前/后翻滚一小段距离（10f 全身无敌 + 4f 恢复）
- 空中不可使用
- 可取消防御硬直（消耗能量）

```json
// data/config.json 新增
"dodge": {
    "duration": 22,
    "invuln_start": 1,
    "invuln_end": 14,
    "recovery": 8,
    "distance": 80,
    "meter_cost": 0
}
```

### 7.3 防御取消·吹飞攻击（Guard Cancel CD）

- 条件：防御硬直中、至少 1 条气
- 输入：C+D（重拳+重脚同时）
- 效果：消耗 1 条气，击飞对手，清除自身防御硬直
- 发生：即时（1f），带无敌帧

```python
def try_guard_cancel(self):
    if self.fsm.state not in (ActionState.BLOCKSTUN, ActionState.BLOCK):
        return False
    if self.power_gauge < METER_PER_STOCK:
        return False
    self.consume_meter(METER_PER_STOCK)
    self.start_move(load_move(f"{self.char_id}/guard_cancel"))
    return True
```

### 7.4 防御取消·紧急回避（Guard Cancel Dodge）

- 防御硬直中 A+B → 消耗 1 条气，翻滚脱离

---

## Phase 8 — 连招系统深化

### 8.1 伤害衰减

```python
class ComboTracker:
    combo_count: int = 0
    damage_scaling: float = 1.0
    
    def apply_scaling(self, base_damage: int) -> int:
        """每次命中后 scaling × 0.85，最低 0.2"""
        dmg = int(base_damage * self.damage_scaling)
        self.damage_scaling = max(0.2, self.damage_scaling * 0.85)
        self.combo_count += 1
        return dmg
    
    def reset(self):
        self.combo_count = 0
        self.damage_scaling = 1.0
```

KOF 特有的**修正**：
- 超必杀技作为连招收尾时，有最低伤害保证（至少 40% 基础伤害）
- 同一技能在一次连招中使用 2 次以上，修正更重（×0.7）

### 8.2 Cancel 层级

```
普攻 ──cancel──→ 特殊技 ──cancel──→ 必杀技 ──cancel──→ 超必杀技
  │                                    │
  └── 不可直接 cancel 到超必 ──────────┘（需要 super cancel 窗口）
```

大部分 KOF 角色遵循：**普攻 → 特殊技 → 必杀技 → 超必** 的链式取消规则。

### 8.3 HUD 连招显示

右上角实时显示：
```
15 HITS
DMG: 320
```

---

## Phase 9 — 组队对战（3v3）

### 9.1 Team 数据结构

```python
@dataclass
class TeamMember:
    char_id: str            # 角色 ID（如 "kyo", "iori", "daimon"）
    order: int              # 出场顺序 0/1/2
    health_remaining: int   # 剩余血量（下场时）

class Team:
    members: list[TeamMember]     # 3 人
    active_index: int = 0         # 当前场上角色索引
    
    @property
    def active(self) -> TeamMember:
        return self.members[self.active_index]
    
    def next_member(self) -> Optional[TeamMember]:
        """当前角色死亡时，选择下一位出战"""
        for m in self.members:
            if m.health_remaining > 0:
                return m
        return None  # 全员战败
    
    def is_defeated(self) -> bool:
        return all(m.health_remaining <= 0 for m in self.members)
```

### 9.2 回合流转

```
角色选择 → 1P-1 vs 2P-1 → 胜者留场（微量回血）→ 败者换人
         → 1P-1 vs 2P-2 → ... 
         → 直到一方 3 人全部战败
```

KOF 特色：**胜者少量回血**（通常恢复最后一场受到伤害的 30%）。

```python
ROUND_RECOVERY_RATIO = 0.3  # 胜者回血比例

def apply_round_recovery(winner: Fighter):
    """每回合结束后胜者微量恢复"""
    dmg_taken = MAX_HEALTH - winner.health
    recovery = int(dmg_taken * ROUND_RECOVERY_RATIO)
    winner.health = min(MAX_HEALTH, winner.health + recovery)
```

### 9.3 角色选择界面

新增 `CharacterSelectState`：

```
┌──────────────────────────────────────────────┐
│             SELECT YOUR FIGHTER               │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐  │
│  │KYO │ │IORI│ │DAI │ │TER │ │RALF│ │CLA │  │
│  │    │ │    │ │MON │ │RY  │ │    │ │RK  │  │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘  │
│  P1: [1.  ][2.  ][3.  ]                      │
│  P2: [1.  ][2.  ][3.  ]                      │
└──────────────────────────────────────────────┘
```

---

## Phase 10 — 角色数据系统

### 10.1 角色定义 JSON

```json
// data/characters/kyo.json
{
    "id": "kyo",
    "name": "草薙京",
    "display_name": "KYO KUSANAGI",
    "portrait": "kyo_portrait.png",
    "stats": {
        "walk_speed": 4.5,
        "dash_speed": 7.0,
        "jump_velocity": -16.0,
        "super_jump_velocity": -18.0,
        "hop_velocity": -9.0,
        "health": 100,
        "guard_gauge": 100
    },
    "moves": {
        "normals": {
            "far_a": "far_a.json",
            "far_b": "far_b.json",
            "far_c": "far_c.json",
            "far_d": "far_d.json",
            "close_a": "close_a.json",
            "close_c": "close_c.json",
            "close_d": "close_d.json",
            "crouch_a": "crouch_a.json",
            "crouch_b": "crouch_b.json",
            "crouch_c": "crouch_c.json",
            "crouch_d": "crouch_d.json",
            "jump_a": "jump_a.json",
            "jump_b": "jump_b.json",
            "jump_c": "jump_c.json",
            "jump_d": "jump_d.json"
        },
        "command_normals": {
            "f_b": "f_b.json"
        },
        "specials": {
            "qcf_p": "qcf_p.json",
            "dp_p": "dp_p.json",
            "qcb_k": "qcb_k.json",
            "hcb_p": "hcb_p.json"
        },
        "supers": {
            "qcf_qcf_p": "qcf_qcf_p.json",
            "qcb_hcf_p": "qcb_hcf_p.json"
        }
    }
}
```

### 10.2 角色初始阵容

| 角色 | 风格 | 代表技 |
|------|------|--------|
| 草薙京 (Kyo) | 波升系 | 暗拂 / 鬼烧 / 胧车 / 大蛇薙 |
| 八神庵 (Iori) | 近战压制 | 暗拂(地) / 葵花 / 屑风 / 八稚女 |
| 不知火舞 (Mai) | 机动/飞道具 | 花蝶扇 / 龙炎舞 / 超必杀忍蜂 |
| 坂崎良 (Ryo) | 打击系 | 虎煌拳 / 虎炮 / 飞燕疾风脚 / 霸王翔吼拳 |
| 克拉克 (Clark) | 投技系 | 超级阿根廷攻击 / 弗兰肯斯坦纳 |
| 拉尔夫 (Ralf) | 打击+突进 | 机炮拳 / 拉尔夫踢 / 超级机炮拳 |

---

## Phase 11 — 打击感与表现力

### 11.1 Hitstop 增强

| 攻击类型 | Hitstop (双方)|
|----------|--------------|
| 轻攻击 | 8f |
| 重攻击 | 12f |
| 必杀技 | 14f |
| 超必杀 | 18-22f |
| 投技 | 4f |

Hitstop 期间画面短暂定格（除 UI 外），屏幕震动。

### 11.2 屏幕震动

```python
@dataclass
class ScreenShake:
    intensity: float     # 当前强度（衰减中）
    duration: int        # 剩余帧数
    def offset(self) -> tuple[int, int]:
        if self.duration <= 0:
            return (0, 0)
        rand_x = random.uniform(-self.intensity, self.intensity)
        rand_y = random.uniform(-self.intensity, self.intensity)
        return (int(rand_x), int(rand_y))
```

震动触发规则：
- 轻攻击命中：intensity=2, duration=6
- 重攻击命中：intensity=4, duration=10
- 必杀技命中：intensity=6, duration=14
- 超必杀命中：intensity=10, duration=20
- KO：intensity=16, duration=30

### 11.3 粒子效果

```python
class ParticleType(Enum):
    HIT_SPARK = auto()      # 命中火花（橙/黄色）
    BLOCK_SPARK = auto()    # 防御火花（白/蓝色）
    BLOOD = auto()          # 血液（极少使用，KOF 风格偏清爽）
    DUST = auto()           # 落地/移动灰尘
    ENERGY = auto()         # 能量/气功波特效
    SUPER_FLASH = auto()    # 超必杀暗转特效
```

### 11.4 超必杀暗转（Super Freeze）

超必杀发动时：
1. 画面变暗（半透明黑色覆盖层）
2. 角色特写/头像闪现
3. 持续 ~15f
4. 恢复后进入 startup 阶段

```python
class SuperFreeze:
    active: bool = False
    duration: int = 15
    portrait: Surface = None   # 发动方角色特写
    
    def draw(self, screen):
        # 全屏 50% 黑色遮罩
        dark_overlay = pygame.Surface((SCREEN_W, SCREEN_H))
        dark_overlay.set_alpha(128)
        dark_overlay.fill(BLACK)
        screen.blit(dark_overlay, (0, 0))
        # 角色特写
        if self.portrait:
            screen.blit(self.portrait, (SCREEN_W // 2 - 100, SCREEN_H // 2))
```

---

## Phase 12 — 音效系统

### 12.1 音效分级

```
优先级 (Channel 0 最高):
Channel 0: 语音（KO 叫声、超必杀喊招）
Channel 1: 超必杀/必杀技命 中
Channel 2: 普攻命中/防御
Channel 3: 移动、跳跃、菜单
Channel 4: 背景音乐
```

### 12.2 最少音效列表

| 分类 | 音效 | 数量 |
|------|------|------|
| 打击 | 轻/中/重命中 | 3 |
| 防御 | 站防/蹲防 | 2 |
| 语音 | KO/必杀喊招 | 5+ |
| UI | 菜单移动/确认/取消 | 3 |
| 环境 | 倒计时/回合开始 | 2 |
| BGM | 各场景/角色主题曲 | 3+ |

---

## 实现顺序

```
Phase 1   [完成] 战斗核心：Hitbox/Hurtbox / 防御 / 硬直 / 击退 / 帧数据 / FSM
Phase 2   [2-3周] 4 键系统：Action 扩展 / 组合键 / 蹲姿 / 近远普攻判定
Phase 3   [1-2周] 移动系统：Dash/Backdash / Hop/超跳 / 跑跳
Phase 4   [2-3周] 必杀技：指令识别引擎 / 波动/升龙/蓄力 / 角色招式库
Phase 5   [1-2周] 能量槽：Power Gauge / MAX 模式 / 超必杀 / 防御取消
Phase 6   [1-2周] 投技：普投 / 拆投 / 指令投
Phase 7   [1-2周] 防御扩展：蹲防/站防规则 / 中段/下段判定 / Dodge / GCD
Phase 8   [1-2周] 连招深化：ComboTracker / 伤害衰减 / Cancel 层级
Phase 9   [2-3周] 组队对战：Team / 角色选择 / 回合流转 / 回血
Phase 10  [1-2周] 角色数据：角色 JSON 定义 / 招式数据库 / 初始 6 角色
Phase 11  [2-3周] 表现力：粒子 / 震动 / 暗转 / 相机 / 精灵表 / 舞台
Phase 12  [1-2周] 音效：SoundManager / 分级播放 / 音效资源
工程改进  [穿插] 事件总线 / SOCD / 负边沿 / Schema 校验 / 手柄

总计估算：16～28 周（单人全职）
```

---

## 关键设计决策

1. **KOF 无空中防御**。与街霸不同，这是 KOF 的核心差异化特征，影响防御判定和跳跃攻击的博弈。
2. **4 键布局是 KOF 的根基**。普攻/必杀/投技/回避全部基于 A/B/C/D 的组合，组合键检测是输入系统的核心。
3. **中段/下段 二择是攻防核心**。蹲防不怕下段但怕中段，站防不怕中段但怕下段，这决定了 KOF 的压制与破防逻辑。
4. **Cancel 层级链**（普攻→特殊→必杀→超必）比街霸更严格。不能跳过层级直接取消。
5. **3v3 组队**需要更多 UI 和状态管理工作。建议先用 1v1 完成所有战斗系统后，再加组队系统。
6. **浮点数问题**：回滚网络需要的确定性模拟仍然建议用定点数（int 型位置单位）。
7. **不引入 ECS**。当前 OOP 粒度对格斗游戏正合适，每个 Fighter 的状态和行为内聚性很强。
