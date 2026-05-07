import asyncio
from collections import deque
from dataclasses import dataclass
import inspect
from typing import Any, Optional, Union

@dataclass
class Message:
    topic: str
    content: Optional[Any] = None
    sender: Optional[str] = None

class MessageBus:
    def __init__(self):
        self.mailboxes = {}
        self.subscribers = {}
    
    def register(self, name: str) -> 'Mailbox':
        """注册一个新的信箱，并返回它的实例"""
        if name in self.mailboxes:
            return self.mailboxes[name]  # 已经注册过了，直接返回现成的信箱实例
        mailbox = Mailbox()
        self.mailboxes[name] = mailbox
        return mailbox
    
    async def send_to(self, recipient: Union[str, "Mailbox"], message: Message):
        """发送消息到指定收件人的信箱"""
        if isinstance(recipient, str):
            if recipient not in self.mailboxes:
                raise ValueError(f"Recipient '{recipient}' does not have a registered mailbox.")
            await self.mailboxes[recipient].send(message)
        else:
            await recipient.send(message)

    def subscribe(self, topic: str, subscriber : Union["Mailbox", callable]):
        """订阅某主题的广播消息"""
        if callable(subscriber):
            self.subscribers.setdefault(topic, []).append(subscriber)
        elif isinstance(subscriber, Mailbox):
            self.subscribers.setdefault(topic, []).append(subscriber.send)

    async def publish(self, topic: str, data):
        message = Message(topic=topic, content=data)
        tasks = []
        # 1. 收集所有的 Mailbox 发送任务
        # 注意：这里直接调用 inbox.send，因为你在 subscribe 里存的是方法引用
        for subscriber in self.subscribers.get(topic, []):
            if inspect.iscoroutinefunction(subscriber):
                tasks.append(subscriber(message))
            else:
                subscriber(message)

        # 3. 并发执行所有任务
        if tasks:
            # return_exceptions=True 可以防止某个订阅者报错导致整个发布流程崩溃
            await asyncio.gather(*tasks, return_exceptions=True)
        

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