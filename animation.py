"""动画系统 — AnimFrame / Anim / Animator"""

from typing import Callable, Optional, List


class AnimFrame:
    """单帧：绘制函数 + 持续帧数 + 碰撞盒数据"""
    def __init__(self, draw: Callable, duration: int = 4,
                 hitboxes: Optional[List] = None,
                 hurtboxes: Optional[List] = None):
        self.draw = draw          # draw(surface, x, y, facing_right, **kwargs)
        self.duration = duration  # 该帧持续的游戏帧数
        self.hitboxes: List = hitboxes or []   # CollisionBox 列表
        self.hurtboxes: List = hurtboxes or [] # CollisionBox 列表


class Anim:
    """命名动画：帧序列 + 循环模式"""
    def __init__(self, name: str, frames: list[AnimFrame], loop: bool = True):
        self.name = name
        self.frames = frames
        self.loop = loop
        self.frame_idx = 0
        self.timer = 0
        self.finished = False

    def reset(self):
        self.frame_idx = 0
        self.timer = 0
        self.finished = False

    def tick(self):
        """推进一帧，返回 True 表示动画结束（非循环动画首帧完成时）"""
        if not self.frames:
            return False
        self.timer += 1
        frame = self.frames[self.frame_idx]
        if self.timer >= frame.duration:
            self.timer = 0
            if self.frame_idx < len(self.frames) - 1:
                self.frame_idx += 1
            else:
                if self.loop:
                    self.frame_idx = 0
                else:
                    self.finished = True
                    return True
        return False

    @property
    def current_frame(self) -> Optional[AnimFrame]:
        if self.frames:
            return self.frames[self.frame_idx]
        return None


# 帧绘制函数签名
DrawFunc = Callable[..., None]


class Animator:
    """
    管理一组动画，根据当前状态播放对应动画。
    使用方式：
        animator.add("idle", idle_anim)
        animator.play("idle")
        animator.tick()           # 每帧调用
        animator.draw(surf, x, y, facing_right, color=..., dark_color=...)
    """

    def __init__(self):
        self._anims: dict[str, Anim] = {}
        self._current: Optional[Anim] = None
        self._current_name = ""

    def add(self, name: str, anim: Anim):
        self._anims[name] = anim

    def play(self, name: str):
        """切换到指定动画（同名不做重置）"""
        if self._current_name != name:
            self._current = self._anims.get(name)
            self._current_name = name
            if self._current:
                self._current.reset()

    def tick(self):
        if self._current:
            self._current.tick()

    def draw(self, surface, x: float, y: float,
             facing_right: bool, **kwargs):
        """
        绘制当前帧。
        kwargs 会透传给帧绘制函数，通常包括 color、dark_color、color_override 等。
        """
        if self._current is None:
            return
        frame = self._current.current_frame
        if frame is None:
            return
        frame.draw(surface, int(x), int(y), facing_right, **kwargs)

    @property
    def current_frame(self) -> Optional[AnimFrame]:
        """当前帧（含碰撞盒数据）"""
        if self._current:
            return self._current.current_frame
        return None

    @property
    def current_name(self) -> str:
        return self._current_name

    @property
    def finished(self) -> bool:
        """当前（非循环）动画是否播放完毕"""
        return self._current.finished if self._current else True