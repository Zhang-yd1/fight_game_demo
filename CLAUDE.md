# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
python game.py
python test_input_system.py   # 运行测试
```

Requires Python 3.13+ and pygame 2.6+.

## Architecture

Pygame 双人对战格斗游戏，基于 FSM 状态机 + 数据驱动配置。

### 文件职责

| 文件 | 职责 |
|---|---|
| `config.py` | 从 `data/config.json` 加载所有可调参数，提供模块级常量 |
| `data/config.json` | **唯一配置入口**：窗口、颜色、物理、战士属性、攻击帧数据、HUD、键位绑定 |
| `fighter.py` | `Fighter` 类：物理、移动、攻击、碰撞、渲染、血量条 |
| `input_system.py` | `Action` 枚举 + `KeyConfig` + `InputBuffer` + `InputManager` |
| `render.py` | 场景渲染：背景、HUD、结果面板、菜单、暂停覆盖层 |
| `states.py` | 状态机核心：`GameState` 基类 + 4 个具体状态 + `GameContext` |
| `game.py` | 主入口：状态注册、主循环（QUIT 统一处理 + input.update + 状态调度） |

### 数据驱动配置

`data/config.json` 集中管理所有游戏参数，修改后重启即可生效，无需改代码：

- **`window`** — 窗口尺寸、标题、帧率
- **`colors`** — 12 种颜色（RGB 数组）
- **`ground`** / **`physics`** — 地面高度、重力、跳跃初速
- **`fighter`** — 战士尺寸、血量上限、移速
- **`attack`** — 伤害、持续帧、冷却帧、判定框尺寸、闪烁帧数
- **`round`** — 回合时长
- **`hud`** — 血量条尺寸、HUD 高度
- **`keybinds`** — P1/P2 键位（可用英文键名，如 `"a"`, `"left"`, `"escape"`, `"kp0"`）

`config.py` 在导入时解析 JSON，将键名字符串转为 pygame keycode，构建 `KeyConfig` 对象。

### 状态机设计

```
Menu ──Enter──→ Fight ──ESC──→ Pause ──ESC──→ Fight
  ↑               │                │  Q         │
  └──ESC──────────┘                └──→ Menu ←──┘
                   │                           ↑
                   └──(死亡/超时)──→ Result ──R/ESC─┘
```

### 关键设计决策

- 坐标系统：`Fighter.x/y` 为战士**左上角**，`GROUND_Y=460` 是脚底位置
- 攻击判定：`attack_timer == ATTACK_DURATION`（首帧检测），`check_attack()` 必须在 `update()` 之前调用
- 朝向强制：每帧根据 `p1.x < p2.x` 重置双方朝向
- 输入系统：`InputManager` 每帧轮询 `get_pressed()`，提供 `is_held()` 和 `just_pressed()`，QUIT 事件在主循环统一处理
- 输入缓冲：`InputBuffer` 记录 (Action, 帧号) 序列，`has_sequence()` 为连招检测预留