import os
import re
import time
import asyncio
import logging
import inspect
import warnings
from typing import List, Callable, Optional

class SubprocessRunner:
    """子进程监控器 (异步版)：负责启动、观察、回调和停止一个外部进程。"""

    def __init__(
        self,
        commands: List[str],
        name: str,
        ready_match: str = r".*",
        log_path: str = "logs",
        callback_match: str = r"^(?!x)x$",  # 永远不会匹配的正则表达式
        callback: Optional[Callable] = None,
        finished_callback: Optional[Callable] = None,
    ):
        self.commands = commands
        start_time = time.strftime("%Y%m%d_%H%M%S")
        self.name = name

        # 初始化日志
        self.logger = logging.getLogger(name)
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        handler = logging.FileHandler(f"{log_path}/{start_time}.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # 运行态对象：asyncio 子进程句柄
        self.process: Optional[asyncio.subprocess.Process] = None
        self._monitor_task: Optional[asyncio.Task] = None

        # 正则表达式预编译，提升循环内匹配性能
        self.ready_match = re.compile(ready_match)
        self.callback_match = re.compile(callback_match)

        # 就绪状态控制
        self.ready_event = asyncio.Event()
        self.ready_line = None

        # 回调配置
        self.callback = callback
        self.finished_callback = finished_callback

    async def _start(self):
        """内部启动流程（作为后台异步任务运行）。"""
        self.logger.info(f"使用此命令启动子进程： {self.commands}")

        # 1. 异步拉起子进程
        self.process = await asyncio.create_subprocess_exec(
            *self.commands,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        print(f"子进程 {self.name} 已启动, PID为 {self.process.pid}.")

        # 2. 逐行异步读取输出
        while True:
            line_bytes = await self.process.stdout.readline()
            if not line_bytes:
                break  # EOF，进程输出结束

            # 解码并去除末尾换行符
            line = line_bytes.decode(errors="replace").strip()
            self.logger.info(line)

            # 检查就绪状态
            if not self.ready_event.is_set() and self.ready_match.search(line):
                self.ready_line = line
                self.logger.info("子进程已就绪.")
                self.ready_event.set()

            # 检查业务回调
            if self.callback and self.callback_match.search(line):
                if inspect.iscoroutinefunction(self.callback):
                    await self.callback()  # 支持 async def 的回调
                else:
                    self.callback()        # 支持普通的 def 回调

        # 3. 等待进程彻底结束
        await self.process.wait()

        # 4. 如果进程提前退出且从未命中 ready_match，也要释放等待
        if not self.ready_event.is_set():
            self.ready_event.set()
            warnings.warn(f"子进程 {self.name} 启动失败或异常退出.")

        # 5. 执行结束回调
        if self.finished_callback:
            if inspect.iscoroutinefunction(self.finished_callback):
                await self.finished_callback()
            else:
                self.finished_callback()

    async def run(self):
        """异步启动子进程，并阻塞等待“就绪或失败”。"""
        self.ready_event.clear()
        self.ready_line = None

        # 使用 create_task 将 _start 放入后台执行，不阻塞当前协程
        self._monitor_task = asyncio.create_task(self._start())

        # 主协程挂起，直到后台任务 set 了 ready_event
        await self.ready_event.wait()

    async def stop(self):
        """优雅且异步地终止子进程。"""
        self.logger.info("正在终止子进程.")
        # asyncio 的 process 使用 returncode 来判断是否结束
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()  # 必须 await wait()，防止产生僵尸进程

        # 如果后台监听任务还在跑，取消它
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    @property
    def is_running(self):
        """当前子进程是否仍在运行。"""
        if self.process is None:
            return False
        # returncode 为 None 说明进程还没死
        return self.process.returncode is None