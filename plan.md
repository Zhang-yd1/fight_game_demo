# 格斗游戏 — 工业级产品优化方案

## 当前状态评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 战斗系统 | 3/10 | 仅有移动/跳跃/单次攻击，无防御、硬直、击退、帧数据 |
| 动画系统 | 5/10 | Animator 架构良好，但只有程序化绘制，无精灵表支持 |
| 输入系统 | 7/10 | Action/KeyConfig/InputBuffer 架构完整，缺 SOCD/手柄/负边沿 |
| 渲染 | 4/10 | 单一场景、无相机系统、无特效、无图层管理 |
| 音效 | 0/10 | 完全缺失 |
| 网络 | 0/10 | 完全缺失 |
| 工程化 | 5/10 | 模块化不错，但缺事件总线、错误处理、配置校验 |

---

## Phase 1 — 战斗核心（优先级最高）

### 1.1 碰撞系统重构：Hitbox / Hurtbox 分离

当前 `attack_rect` 和 `rect` 用 `colliderect` 直接碰撞，工业级做法：

```python
@dataclass
class CollisionBox:
    """单个碰撞盒（相对角色原点）"""
    offset_x: float     # 相对 Fighter.x 的偏移
    offset_y: float
    width: int
    height: int
    type: str           # "hit" | "hurt" | "throw" | "projectile"
    damage: int = 0
    knockback_x: float = 0.0
    knockback_y: float = 0.0
    hitstun: int = 0    # 命中硬直帧数
    blockstun: int = 0  # 防御硬直帧数
    hitstop: int = 0    # 命中停顿帧数
    chip_damage: int = 0
```

- 每帧攻击动作定义一组 `hitboxes`，每帧非攻击动作定义一组 `hurtboxes`
- 碰撞检测改为 `hitbox ∩ defender.hurtbox`（而非 `attack_rect ∩ body_rect`）
- 碰撞盒数据编入 `data/moves/` 目录下的移帧数据文件（见 §1.5）

### 1.2 防御系统

```python
class Fighter:
    self.is_blocking = False       # 持续按住后退键
    self.block_health = 100        # 防御槽（类似街霸的 drive gauge）
    self.guard_broken = False

def check_block(defender, attacker):
    """后退方向 + 地面 = 站防；后退+下 = 蹲防；空中不可防"""
    if defender.on_ground and defender.is_holding_back(attacker):
        defender.is_blocking = True
        defender.take_chip_damage(attacker.current_move.chip_damage)
        defender.apply_blockstun(attacker.current_move.blockstun)
        # 防御槽减少，归零后破防大硬直
```

### 1.3 硬直系统

```python
# Fighter 新增状态
self.hitstun = 0         # 受击硬直，期间不可操作
self.blockstun = 0       # 防御硬直
self.hitstop = 0         # 命中停顿（双方冻结）
self.knockback_vel = 0.0 # 击退速度

# 状态判定：只有 is_actionable() 为 True 时才响应输入
def is_actionable(self):
    return (self.hitstun == 0 and self.blockstun == 0
            and self.hitstop == 0 and not self.dead
            and self.attack_timer == 0)
```

- 命中时攻击方和防御方同时冻结 `hitstop` 帧（通常 8-14 帧）
- 受击方被打入 `hitstun` 状态，长按后退可提前 1-2 帧解除（受身）
- 空中受击有 `air_hitstun`，落地自动恢复

### 1.4 击退系统

- 每个攻击技指定 KBx/KBy，命中后施加 `knockback_vel`
- 每帧应用摩擦力衰减
- 版边击退衰减（防止无限连）

### 1.5 帧数据

每个动作变为数据驱动，定义在 JSON 中：

```json
// data/moves/ryu/stand_lp.json
{
  "name": "Stand LP",
  "startup": 4,
  "active": 3,
  "recovery": 7,
  "frames": [
    { "stage": "startup", "duration": 4, "hurtboxes": [{"x":10,"y":0,"w":30,"h":80}] },
    { "stage": "active",  "duration": 3,
      "hitboxes": [
        {"x":45,"y":20,"w":25,"h":15, "damage":30, "kb_x":2, "kb_y":0, "hitstun":14, "hitstop":8}
      ],
      "hurtboxes": [{"x":10,"y":0,"w":30,"h":80}]
    },
    { "stage": "recovery", "duration": 7, "hurtboxes": [{"x":10,"y":0,"w":30,"h":80}] }
  ],
  "cancel_into": ["stand_mp", "crouch_lk", "hadouken"],
  "cancel_window": [4, 7],
  "on_hit": 3,
  "on_block": -2
}
```

### 1.6 动作状态机

战士内部需要一个 ActionFSM 管理动作流转：

```
IDLE → WALK / JUMP / ATTACK
ATTACK → startup → active → recovery → IDLE
HITSTUN → IDLE (可受身)
BLOCKSTUN → IDLE
```

每个动作有推进规则（只能 cancel 到特定动作在特定窗口期），由帧数据定义。

---

## Phase 2 — 连招深度

### 2.1 连招计数器 + 伤害衰减

```python
class ComboTracker:
    combo_count: int
    total_damage: float
    scaling: float           # 起始 1.0，每次命中 × 0.9
    gravity_scaling: float   # 空中连段时重力逐渐增大
```

- 每次命中 `damage = base_damage * scaling`，然后 scaling *= 0.9
- 受击方脱离 hitstun 后连招重置
- HUD 显示连击数和累计伤害

### 2.2 Cancel 窗口

- 普攻在命中/被防后特定帧窗口内可取消为必杀技/超必杀
- 由帧数据 `cancel_into` 和 `cancel_window` 定义
- InputBuffer 中的方向序列可在 cancel_window 内被消耗

### 2.3 必杀技系统

利用已有的 `InputBuffer.has_sequence()`：

```python
SPECIAL_MOVES = {
    "hadouken": {
        "input": [Action.MOVE_DOWN, Action.MOVE_DOWN_RIGHT, Action.MOVE_RIGHT, Action.ATTACK],
        "window": 15,
    },
    "shoryuken": {
        "input": [Action.MOVE_RIGHT, Action.MOVE_DOWN, Action.MOVE_DOWN_RIGHT, Action.ATTACK],
        "window": 15,
    },
}

def check_special_move(buffer: InputBuffer) -> Optional[str]:
    for name, move in SPECIAL_MOVES.items():
        if buffer.has_sequence(move["input"], move["window"]):
            return name
    return None
```

- 必杀技有独立帧数据、更高的伤害/硬直、无敌帧
- 超必杀需消耗能量槽发动

### 2.4 能量系统

```python
class Fighter:
    super_meter: int = 0     # 0~300，一个超必消耗 100
    max_drive: int = 100

# 攒气途径：造成伤害、受到伤害、前进、使用必杀技
```

---

## Phase 3 — 表现力

### 3.1 粒子系统 / VFX

```python
class Particle:
    x, y, vx, vy, life, color, size

class ParticleSystem:
    particles: list[Particle]
    def emit(self, template, position, count):
    def update(self):
    def draw(self, surface, camera_offset):
```

- 命中火花（attack.type → 颜色）
- 防御火花（白色圆形）
- 移动灰尘
- 必杀技光效

### 3.2 屏幕震动

```python
class ScreenShake:
    intensity: float   # 衰减中
    duration: int
    def offset(self) -> tuple[int, int]:
        t = random.uniform(-intensity, intensity)
```

### 3.3 音效系统

```python
class SoundManager:
    sounds: dict[str, Sound]
    def play(self, name: str, volume: float = 1.0, pan: float = 0.0):
    def play_voice(self, move_name: str):
```

- 最少音效：命中、防御、轻/重攻击、跳跃、KO、倒计时、菜单移动/确认
- 通过 `pygame.mixer.Channel` 管理优先级（语音 > 必杀 > 普攻）

### 3.4 精灵表支持

扩展 Animator 支持两种帧模式：

```python
class AnimFrame:
    draw: Optional[Callable] = None     # 程序化绘制函数
    sprite_rect: Optional[Rect] = None  # 精灵表中的矩形
    # 二者互斥

class Animator:
    def __init__(self, sprite_sheet: Optional[Surface] = None):
        ...
```

- 程序化绘制作为 fallback，精灵表优先
- `data/sprites/` 目录存放 png 精灵表 + json 描述文件

### 3.5 相机系统

```python
class Camera:
    x: float
    def update(self, p1: Fighter, p2: Fighter):
        """居中于两人连线中点，限制不超过舞台边界"""
    def apply(self, rect: Rect) -> Rect:
```

### 3.6 舞台系统

- 背景分层（视差滚动）
- 舞台边界（大于屏幕宽度）
- 墙角破坏效果（可选）

---

## Phase 4 — 网络对战

### 4.1 确定性模拟

**核心原则：相同初始状态 + 相同输入序列 → 相同状态。**

需要做到：
- 浮点数统一用 `decimal.Decimal` 或 `int`（定点数），或确保 `math` 模块一致性
- 所有随机数使用固定种子 PRNG（`random.Random(seed)`）
- 帧逻辑与渲染完全分离

### 4.2 状态序列化

```python
def serialize_fighter(f: Fighter) -> bytes:
    """序列化所有需要同步的状态（位置、速度、状态、血量等）"""

def serialize_input(input_manager: InputManager) -> bytes:
    """序列化本帧输入（几个字节）"""

def checksum(state_bytes: bytes) -> int:
    """CRC32 用于对局一致性校验"""
```

### 4.3 回滚网络（Rollback Netcode）

```
输入延迟: N 帧（通常 1-3 帧）
回滚窗口: 7-10 帧

1. 本地预测执行，输入延迟 N 帧后发送
2. 收到远程输入后与本地预测比对
3. 若不一致 → 回滚到分歧帧，重新模拟
4. 保存最近 30 帧快照用于快速回滚
```

```python
class RollbackManager:
    frame: int
    state_history: deque[GameStateSnapshot]  # 最近 30 帧
    input_history: deque[bytes]

    def save_snapshot(self, state): ...
    def rollback_to(self, frame: int): ...
    def resimulate(self, from_frame: int): ...
```

### 4.4 UDP 传输层

```python
class NetplaySession:
    socket: socket.socket       # UDP
    remote_addr: tuple
    local_port: int
    sync_state: str             # "syncing" | "playing" | "disconnected"

    def send_input(self, frame: int, input_bytes: bytes):
    def recv_input(self) -> Optional[bytes]:
    def handle_disconnect(self, timeout_frames: int = 180):
```

---

## 工程化改进

### E1. 事件总线

```python
class Event:
    PLAYER_HIT, PLAYER_BLOCK, PLAYER_KO, ROUND_START, ROUND_END,
    COMBO_UPDATE, METER_CHANGE, SPECIAL_MOVE, PAUSE, RESUME

class EventBus:
    _listeners: dict[Event, list[Callable]]
    def emit(self, event: Event, **data):
    def on(self, event: Event, callback):
```

好处：粒子系统听 `PLAYER_HIT` 生成火花、音效系统听 `PLAYER_HIT` 播放击中音效、HUD 听 `COMBO_UPDATE` 更新连击显示。各系统完全解耦。

### E2. SOCD 清洗

```python
def resolve_socd(held: set[Action]) -> set[Action]:
    """同时按左右 → 无输入（或根据规则返回单个方向）"""
    if Action.MOVE_LEFT in held and Action.MOVE_RIGHT in held:
        held = held - {Action.MOVE_LEFT, Action.MOVE_RIGHT}
    if Action.JUMP in held and Action.CROUCH in held:
        held = held - {Action.CROUCH}  # 上优先
    return held
```

### E3. 负边沿检测

```python
def just_released(self, action: Action) -> bool:
    """本帧刚松开的按键"""
```

用于：长按后退持续防御、松开后立即解除防御；蓄力技松开触发。

### E4. 配置 Schema 校验

```python
from jsonschema import validate

CONFIG_SCHEMA = {
    "type": "object",
    "required": ["window", "ground", "physics", "fighter", "attack", "round"],
    "properties": {
        "window": {"type": "object", "required": ["width", "height", "fps"]},
        ...
    }
}
validate(instance=config_json, schema=CONFIG_SCHEMA)
```

### E5. 字体缓存

```python
# 当前每次 draw_health_bar 都创建 Font 对象 → 内存泄漏
# 改为在 GameContext 中统一管理
ctx.fonts = {
    'hud': pygame.font.SysFont("Arial", 14, bold=True),
    'hud_big': pygame.font.SysFont("Arial", 18, bold=True),
    'result': pygame.font.SysFont("SimHei", 56, bold=True),
    ...
}
```

### E6. 手柄支持

```python
class GamepadManager:
    def map_gamepad_to_actions(self, joystick: pygame.joystick.JoystickType):
        # D-pad / 左摇杆 → 方向
        # 按钮 → ATTACK / JUMP / PAUSE 等
```

通过 `pygame.joystick` + 可配置的键位映射（手柄键码也写入 config.json）。

### E7. 回放系统

确定性模拟天然支持回放：保存每帧输入序列 + 初始状态 + 种子 → 重放。

`data/replays/` 目录存放 `.rpl` 文件（压缩后的输入序列）。

---

## 实施顺序

```
Phase 1 (2-3 周)    战斗核心：Hitbox/Hurtbox → 防御 → 硬直 → 击退 → 帧数据
Phase 2 (1-2 周)    连招深度：Combo 计数 → 伤害衰减 → Cancel → 必杀技 → 能量
Phase 3 (1-2 周)    表现力：VFX 粒子 → 屏幕震动 → 音效 → 精灵表 → 相机
Phase 4 (2-4 周)    网络：确定性模拟 → 序列化 → Rollback → UDP
工程改进 (穿插进行)   事件总线 → SOCD → 负边沿 → Schema 校验 → 手柄
```

## 关键设计决策

1. **不同语言版本的 Python 浮点一致性不是绝对的**。正式网络对战时建议用 `int` 定点数（如位置单位用 1/1000 像素），或全部帧逻辑用整数运算。
2. **帧逻辑和渲染必须可以在不同频率运行**。战斗逻辑固定 60fps tick，渲染用 `dt` 插值做平滑。
3. **回滚网络是这个架构最困难的部分**。建议先做本地双人对战后，直接跳到回滚原型验证核心假设。
4. **不建议引入 ECS**。当前 OOP 粒度对一个 2 角色格斗游戏正合适，ECS 的间接开销对确定性模拟也不友好。