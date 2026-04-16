import time
import re
import warnings
from typing import List

import psutil
import subprocess
import logging
import threading


class SubprocessMonitor:
    """子进程监控器：负责启动、观察、回调和停止一个外部进程。

    设计目标：
    1) 统一子进程启动方式，并将标准输出写入日志；
    2) 基于正则表达式判断“进程就绪”时机；
    3) 支持在输出命中指定模式时触发业务回调；
    4) 提供线程化启动与阻塞等待，简化上层调用。

    典型使用场景：
    - 启动 Mineflayer/Node 服务并等待 “Server started ...” 再继续；
    - 持续收集服务输出到日志文件，便于排障；
    - 进程结束时触发清理逻辑（finished_callback）。
    """

    def __init__(
        self,
        commands: List[str],
        name: str,
        ready_match: str = r".*",
        log_path: str = "logs",
        callback_match: str = r"^(?!x)x$",  # 永远不会匹配的正则表达式
        callback: callable = None,
        finished_callback: callable = None,
    ):
        """初始化监控器配置。

        参数说明：
        - commands: 子进程启动命令（列表形式，等价于 shell 的 argv）；
        - name: 进程名称，用于日志命名和打印标识；
        - ready_match: 就绪判定正则，命中后解除 run() 的等待；
        - log_path: 日志目录，日志文件按时间戳命名；
        - callback_match: 回调触发正则，命中后调用 callback；
        - callback: 输出命中 callback_match 时执行的函数；
        - finished_callback: 子进程输出循环结束后执行的函数。
        """
        self.commands = commands
        # 以启动时间作为日志文件名，避免覆盖历史记录。
        start_time = time.strftime("%Y%m%d_%H%M%S")
        self.name = name

        # 初始化文件日志：每个子进程实例独立一个日志文件。
        self.logger = logging.getLogger(name)
        handler = logging.FileHandler(f"{log_path}/{start_time}.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # 运行态对象：真实子进程句柄。
        self.process = None

        # 就绪检测相关状态。
        self.ready_match = ready_match
        self.ready_event = None
        self.ready_line = None

        # 输出回调相关配置。
        self.callback_match = callback_match
        self.callback = callback
        self.finished_callback = finished_callback

        # 后台读取线程（避免阻塞主线程）。
        self.thread = None

    def _start(self):
        """内部启动流程（在线程中运行）。

        工作步骤：
        1) 拉起子进程并合并 stdout/stderr；
        2) 持续逐行读取输出并写日志；
        3) 命中 ready_match 时设置 ready_event；
        4) 命中 callback_match 时执行 callback；
        5) 进程退出后执行 finished_callback（如有）。
        """
        self.logger.info(f"使用此命令启动子进程： {self.commands}")

        # 使用 psutil.Popen 便于统一检查进程状态与终止。
        self.process = psutil.Popen(
            self.commands,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        print(f"子进程 {self.name} 已启动, PID为 {self.process.pid}.")

        # 逐行读取输出：
        # - 写入日志；
        # - 检查是否就绪；
        # - 检查是否触发业务回调。
        for line in iter(self.process.stdout.readline, ""):
            self.logger.info(line.strip())
            if re.search(self.ready_match, line):
                self.ready_line = line
                self.logger.info("子进程已就绪.")
                self.ready_event.set()
            if re.search(self.callback_match, line):
                self.callback()

        # 如果进程提前退出且从未命中 ready_match，也要释放等待，避免死等。
        if not self.ready_event.is_set():
            self.ready_event.set()
            warnings.warn(f"子进程 {self.name} 启动失败.")

        # 子进程生命周期结束后的收尾回调。
        if self.finished_callback:
            self.finished_callback()

    def run(self):
        """异步启动子进程，并阻塞等待“就绪或失败”。

        注意：
        - run() 返回并不代表进程长期稳定运行；
        - 它只保证 _start() 已经判定“就绪”或“启动失败”。
        """
        # 每次 run 前重置就绪同步对象和就绪行。
        self.ready_event = threading.Event()
        self.ready_line = None

        # 后台线程执行真正的启动与输出监听逻辑。
        self.thread = threading.Thread(target=self._start)
        self.thread.start()

        # 主线程等待直到 _start() 设置 ready_event。
        self.ready_event.wait()

    def stop(self):
        """终止子进程并等待其退出。"""
        self.logger.info("正在终止子进程.")
        if self.process and self.process.is_running():
            self.process.terminate()
            self.process.wait()

    # def __del__(self):
    #     if self.process.is_running():
    #         self.stop()

    @property
    def is_running(self):
        """当前子进程是否仍在运行。"""
        if self.process is None:
            return False
        return self.process.is_running()
