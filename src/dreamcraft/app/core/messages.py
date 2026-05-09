import inspect
import asyncio
from collections import deque
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, overload
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dreamcraft.domain import Waypoint

class Message(BaseModel):
    topic: str
    content: Optional[Any] = None
    sender: Optional[str] = None
    
M = TypeVar("M", bound=Message)

class ExecutionFailureMessageContent(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    from_wp: Optional[Waypoint]
    to_wp: Optional[Waypoint]
    reason: Dict[str, Any]  # 可以包含错误类型、错误信息、环境状态等详细信息

class ExecutionFailureMessage(Message):
    topic: str = "exec_fail"
    content: ExecutionFailureMessageContent = Field(default_factory=ExecutionFailureMessageContent)

    @model_validator(mode='before')
    @classmethod
    def wrap_content(cls, data: Any) -> Any:
        # 如果用户直接传了 from_wp, to_wp 等，我们手动把它们包进 content 里
        if isinstance(data, dict):
            # 提取属于 content 的字段
            content_data = {
                "from_wp": data.pop("from_wp", None),
                "to_wp": data.pop("to_wp", None),
                "reason": data.pop("reason", {}),
            }
            # 如果真的传了这些字段，就构造 content
            if any(content_data.values()):
                data["content"] = content_data
        return data

    @overload
    def __init__(self, *, from_wp: Waypoint, to_wp: Waypoint, reason: Dict[str, Any]): ...
    @overload
    def __init__(self, *, content: ExecutionFailureMessageContent): ...

    def __init__(self, **data):
        super().__init__(**data) 
    
    @property
    def from_wp(self) -> Optional[Waypoint]:
        return self.content.from_wp if self.content else None
    @property
    def to_wp(self) -> Optional[Waypoint]:
        return self.content.to_wp if self.content else None
    @property
    def reason(self) -> Dict[str, Any]:
        return self.content.reason if self.content else {}
        

class MessageBus:
    def __init__(self):
        self.mailboxes = {}
        self.subscribers = {}
    
    def register(self, name: str) -> 'Mailbox':
        """注册一个新的信箱，并返回它的实例"""
        if name in self.mailboxes:
            return self.mailboxes[name]  # 已经注册过了，直接返回现成的信箱实例
        mailbox = Mailbox()
        mailbox.name = name
        mailbox.bus = self
        self.mailboxes[name] = mailbox
        return mailbox
    
    async def send_to(self, recipient: Union[str, "Mailbox"], message: Message, sender: Union[str] = None):
        """发送消息到指定收件人的信箱"""
        if sender:
            message.sender = sender
        if isinstance(recipient, str):
            if recipient not in self.mailboxes:
                raise ValueError(f"Recipient '{recipient}' does not have a registered mailbox.")
            await self.mailboxes[recipient].post(message)
        else:
            await recipient.post(message)

    def subscribe(self, topic: str, subscriber : Union["Mailbox", callable]):
        """订阅某主题的广播消息"""
        if callable(subscriber):
            self.subscribers.setdefault(topic, []).append(subscriber)
        elif isinstance(subscriber, Mailbox):
            self.subscribers.setdefault(topic, []).append(subscriber.post)

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
        self.name: Optional[str] = None
        self.bus: Optional[MessageBus] = None
        self._queue = asyncio.Queue()
        self._buffer = deque()  # 内部暂存区，用于存放取出来但还不打算处理的信件
        self._waiters: Dict[str, List[asyncio.Future]] = {} # 主题 -> 等待该主题的 Future 列表
    
    async def emit_to(self, target: Union[str, "Mailbox"], message: Message):
        if self.bus:
            await self.bus.send_to(target, message, sender=self)
        else:
            raise RuntimeError("Mailbox is not registered to any MessageBus.")

    async def post(self, message: Message):
        """外界向信箱投递消息：加入了精准拦截逻辑"""
        topic = message.topic
        
        if topic in self._waiters and self._waiters[topic]:
            future = self._waiters[topic].pop(0)

            if not future.done():
                future.set_result(message)
                return

        await self._queue.put(message)

    @overload
    def fetch_topic(self, target_topic: Type[M]) -> Optional[M]: ...
    @overload
    def fetch_topic(self, target_topic: str) -> Optional[Message]: ...

    def fetch_topic(self, target_topic: str | type[Message]) -> Optional[Message]:
        """
        非阻塞尝试获取指定主题的信件。
        不会阻塞主循环，也不会丢失或打乱其他信件的顺序。
        """
        if isinstance(target_topic, type) and issubclass(target_topic, Message):
            target_topic = target_topic.model_fields['topic'].default
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
    
    def fetch(self) -> Optional[Message]:
        """非阻塞获取下一封信件（不区分主题）"""
        # 先看看暂存区里有没有信件
        if self._buffer:
            return self._buffer.popleft()
        
        # 暂存区空了，再看看消息队列里有没有新信件
        try:
            msg = self._queue.get_nowait()
            return msg
        except asyncio.QueueEmpty:
            return None
        


    @overload
    async def wait_for_topic(self, target_topic: Type[M]) -> M: ...
    @overload
    async def wait_for_topic(self, target_topic: str) -> Message: ...

    async def wait_for_topic(self, target_topic: str | type[Message]) -> Message:
        """
        【阻塞版】安全等待特定主题
        """
        if isinstance(target_topic, type) and issubclass(target_topic, Message):
            target_topic = target_topic.model_fields['topic'].default
        # 第一步：先找找看，现在信箱或者暂存区里有没有现成的？
        msg = self.fetch_topic(target_topic)
        if msg:
            return msg

        # 第二步：目前没有。我们需要发个“悬赏令”然后开始休眠等待。
        loop = asyncio.get_running_loop()
        future = loop.create_future() # 创建一个凭证

        # 把自己的凭证加入对应主题的悬赏名单
        self._waiters.setdefault(target_topic, []).append(future)

        # 第三步：阻塞在这里，交出 CPU。
        # 直到 send() 方法发现目标主题，并调用 future.set_result(message) 唤醒我们。
        return await future

    async def receive(self) -> Message:
        """
        兼容传统的按顺序读取（带阻塞）。
        注意：必须先读暂存区里的信，才能保证时间顺序不出错。
        """
        if self._buffer:
            return self._buffer.popleft()
        
        # 暂存区空了，再老老实实去等新信件
        return await self._queue.get()