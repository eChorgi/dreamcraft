import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Message:
    sender: str
    topic: str
    content: Any

class Mailbox:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._buffer = deque()  # 内部暂存区，用于存放取出来但还不打算处理的信件

    async def send(self, message: Message):
        """发送消息（异步）"""
        await self._queue.put(message)

    def try_fetch_topic(self, target_topic: str) -> Optional[Message]:
        """
        【核心功能】非阻塞尝试获取指定主题的信件。
        不会阻塞主循环，也不会丢失或打乱其他信件的顺序。
        """
        # 1. 把 _queue 里所有新到的信全部拿出来，追加到 _buffer 中
        while not self._queue.empty():
            try:
                self._buffer.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        # 2. 遍历手里拿着的信件（_buffer）
        for i, msg in enumerate(self._buffer):
            if msg.topic == target_topic:
                # 3. 找到了！把它从暂存区里抽出来（删除并返回）
                del self._buffer[i]
                return msg

        # 4. 遍历完了也没找到指定主题的信件
        return None

    async def receive(self) -> Message:
        """
        兼容传统的按顺序读取（带阻塞）。
        注意：必须先读暂存区里的信，才能保证时间顺序不出错。
        """
        if self._buffer:
            return self._buffer.popleft()
        
        # 暂存区空了，再老老实实去等新信件
        return await self._queue.get()