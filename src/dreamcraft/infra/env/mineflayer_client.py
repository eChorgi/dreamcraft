import time
import requests
import warnings
import json

from pathlib import Path
from dreamcraft.config import BASE_DIR, LOG_DIR
from dreamcraft.domain.snapshot import Snapshot
from dreamcraft.infra.env.subprocess_runner import SubprocessRunner
from dreamcraft.infra.env.minecraft_instance import MinecraftAzureInstance
from typing import Any, Tuple, Dict


class MinecraftClient():
    def __init__(
        self,
        settings,
        mc_port: int = None,
        azure_login: Dict[str, str] = None,
        mineflayer_host="http://127.0.0.1",
        log_path="./logs",
    ):

        if not mc_port and not azure_login:
            raise ValueError("必须提供 mc_port 或 azure_login 来启动 Minecraft 实例")
        if mc_port and azure_login:
            warnings.warn(
                "azure和Minecraft端口同时提供，优先使用azure启动Minecraft实例"
            )
        self.mc_port = mc_port
        self.azure_login = azure_login
        self.mineflayer_server = f"{mineflayer_host}:{settings.mineflayer_port}"
        self.mineflayer_port = settings.mineflayer_port
        self.request_timeout = settings.mineflayer_request_timeout
        self.log_path = log_path
        self.mineflayer = self.get_mineflayer_process(settings.mineflayer_path, settings.mineflayer_port)
        if settings.azure_login:
            # 按需创建 Minecraft 实例对象（未必立即运行）。
            self.azure_instance = self.get_mc_instance()
        else:
            self.azure_instance = None
        # 是否至少完成过一次 reset；step 前必须为 True。
        self.has_reset = False
        # 保存最近一次 reset 传给后端的配置，供重连时复用。
        self.reset_options = None
        # 是否已与后端建立会话连接。
        self.connected = False
        # 本地维护的暂停状态镜像，避免重复发送 pause 切换请求。
        self.server_paused = False


    def get_mineflayer_process(self, mineflayer_path, server_port):
        (LOG_DIR / "mineflayer").mkdir(parents=True, exist_ok=True)
        return SubprocessRunner(
            commands=[
                "node",
                mineflayer_path,
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=LOG_DIR / "mineflayer",
        )

    
    def check_process(self):
        """确保 Minecraft/Mineflayer 进程可用，并在需要时执行后端 start。"""
        # 如果启用了 mc_instance 且当前未运行，则先拉起 Minecraft。
        if self.azure_instance and not self.azure_instance.is_running:
            print("正在启动 Minecraft 服务器...")
            self.azure_instance.run()
            self.mc_port = self.azure_instance.port
            self.reset_options["port"] = self.azure_instance.port
            print(f"捕获到 Minecraft 服务器端口为: {self.reset_options['port']}")
        retry = 0
        # Mineflayer 挂掉时循环重启；启动后通知后端 /start 建立会话。
        while not self.mineflayer.is_running:
            print("Mineflayer 未运行，正在启动...")
            self.mineflayer.run()
            if not self.mineflayer.is_running:
                if retry > 3:
                    raise RuntimeError("Mineflayer 启动失败")
                else:
                    continue
            print(self.mineflayer.ready_line)
            res = requests.post(
                f"{self.mineflayer_server}/start",
                json=self.reset_options,
                timeout=self.request_timeout,
            )
            if res.status_code != 200:
                # start 失败时停止进程，避免进入不一致状态。
                self.mineflayer.stop()
                raise RuntimeError(
                    f"Minecraft 服务器错误, 状态码: {res.status_code}"
                )
            return res.json()
    
    
    def execute(
        self,
        code: str,
    ) -> Snapshot:
        """执行代码：发送代码到后端，返回环境观测结果。"""
        self.check_process()
        # 执行前恢复运行态，避免在暂停态下 step 无效。
        # self.unpause()
        data = {
            "code": code
        }
        res = requests.post(
            f"{self.mineflayer_server}/step", json=data, timeout=self.request_timeout
        )
        if res.status_code != 200:
            raise RuntimeError(f"调用 Minecraft 服务器失败，状态码: {res.status_code}")
        returned_data = res.json()
        # 执行后重新暂停，便于上层以“离散步”方式控制环境。
        # self.pause()
        return json.loads(returned_data)
    
    def render(self):
        """Gym 接口占位：当前桥接层未实现渲染。"""
        raise NotImplementedError("当前环境桥接未实现 render() 方法")

    def reset(
        self,
        *,
        seed=None,
        options=None,
    ) -> Snapshot:
        """重置环境并返回初始观测。

        支持 hard/soft 重置、初始背包、装备、出生点等配置。
        """
        if options is None:
            options = {}

        # inventory 仅在 hard reset 场景有效（由后端约束）。
        if options.get("inventory", {}) and options.get("mode", "hard") != "hard":
            raise RuntimeError("仅在硬重置模式下可配置初始物品栏")

        # 组装传给后端 /start 的 reset 参数。
        self.reset_options = {
            "port": self.mc_port,
            "reset": options.get("mode", "hard"),
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }

        # 先恢复运行态，再重启 mineflayer，确保 reset 生效。
        self.unpause()
        self.mineflayer.stop()
        time.sleep(1)  # wait for mineflayer to exit

        returned_data = self.check_process()
        self.has_reset = True
        self.connected = True
        # 首次 reset 后，后续 step 内部触发的 reset 默认走 soft，降低开销。
        self.reset_options["reset"] = "soft"
        self.pause()
        return json.loads(returned_data)

    def close(self):
        """关闭会话与子进程，释放资源。"""
        self.unpause()
        if self.connected:
            res = requests.post(f"{self.mineflayer_server}/stop")
            if res.status_code == 200:
                self.connected = False
        if self.azure_instance:
            self.azure_instance.stop()
        self.mineflayer.stop()
        return not self.connected

    def pause(self):
        """将后端切换到暂停态，并同步本地状态位。"""
        if self.mineflayer.is_running and not self.server_paused:
            res = requests.post(f"{self.mineflayer_server}/pause")
            if res.status_code == 200:
                self.server_paused = True
        return self.server_paused

    def unpause(self):
        """将后端从暂停态切回运行态，并同步本地状态位。"""
        if self.mineflayer.is_running and self.server_paused:
            # 后端使用同一个 /pause 接口做状态切换，再次调用即“恢复”。
            res = requests.post(f"{self.mineflayer_server}/pause")
            if res.status_code == 200:
                self.server_paused = False
            else:
                print(res.json())
        return self.server_paused
