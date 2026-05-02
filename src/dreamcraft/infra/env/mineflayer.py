import time
import requests
import warnings
import json

import gymnasium as gym

from pathlib import Path
from dreamcraft.config import BASE_DIR, LOG_DIR
from dreamcraft.infra.env.subprocess_manager import SubprocessManager
from dreamcraft.infra.env.minecraft_launcher import MinecraftInstance
from typing import SupportsFloat, Any, Tuple, Dict
from gymnasium.core import ObsType


class MineflayerClient(gym.Env):
    def __init__(
        self,
        settings,
        mc_port: int = None,
        azure_login: Dict[str, str] = None,
        server_host="http://127.0.0.1",
        log_path="./logs",
    ):
        """初始化环境桥接对象。

        参数说明：
        - mc_port: 已存在 Minecraft 服务端口；
        - azure_login: 启动新 Minecraft 实例所需的登录配置；
        - server_host/server_port: Mineflayer HTTP 服务地址；
        - request_timeout: HTTP 请求超时时间（秒）；
        - log_path: 日志输出目录。
        """
        # 必须二选一：要么连已有端口，要么提供登录信息来拉起实例。
        if not mc_port and not azure_login:
            raise ValueError("必须提供 mc_port 或 azure_login 来启动 Minecraft 实例")
        # 同时提供时，优先使用 azure_login 启动的实例端口。
        if mc_port and azure_login:
            warnings.warn(
                "azure和Minecraft端口同时提供，优先使用azure启动Minecraft实例"
            )
        self.mc_port = mc_port
        self.azure_login = azure_login
        self.server = f"{server_host}:{settings.mineflayer_port}"
        self.server_port = settings.mineflayer_port
        self.request_timeout = settings.mineflayer_request_timeout
        self.log_path = log_path
        # 启动并监控 Mineflayer 子进程（负责和 Minecraft 世界交互）。
        self.mineflayer = self.get_mineflayer_process(settings.mineflayer_port)
        if settings.azure_login:
            # 按需创建 Minecraft 实例对象（未必立即运行）。
            self.mc_instance = self.get_mc_instance()
        else:
            self.mc_instance = None
        # 是否至少完成过一次 reset；step 前必须为 True。
        self.has_reset = False
        # 保存最近一次 reset 传给后端的配置，供重连时复用。
        self.reset_options = None
        # 是否已与后端建立会话连接。
        self.connected = False
        # 本地维护的暂停状态镜像，避免重复发送 pause 切换请求。
        self.server_paused = False


    def get_mineflayer_process(self, server_port):
        """构建并返回 Mineflayer 子进程监控器。"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        current_dir = Path(__file__).resolve().parent
        return SubprocessManager(
            commands=[
                "node",
                str(BASE_DIR/ 'lib' / "mineflayer" / "index.js"),
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path = LOG_DIR / "mineflayer",
        )
    
    def get_mc_instance(self):
        """构建 MinecraftInstance，用于需要时拉起真实 Minecraft 客户端。"""
        print("Creating Minecraft server")
        (LOG_DIR / "minecraft").mkdir(parents=True, exist_ok=True)
        return MinecraftInstance(
            **self.azure_login,
            mineflayer=self.mineflayer,
            log_path = LOG_DIR / "minecraft",
        )
    
    def check_process(self):
        """确保 Minecraft/Mineflayer 进程可用，并在需要时执行后端 start。"""
        # 如果启用了 mc_instance 且当前未运行，则先拉起 Minecraft。
        if self.mc_instance and not self.mc_instance.is_running:
            # if self.mc_instance:
            #     self.mc_instance.check_process()
            #     if not self.mc_instance.is_running:
            print("正在启动 Minecraft 服务器...")
            self.mc_instance.run()
            self.mc_port = self.mc_instance.port
            # 重连时把最新端口写回 reset 参数，保证后端连到正确实例。
            self.reset_options["port"] = self.mc_instance.port
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
                f"{self.server}/start",
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
    
    
    def step(
        self,
        code: str,
        programs: str = "",
    ) -> Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]:
        """执行一步：发送代码到后端，返回环境观测结果。"""
        if not self.has_reset:
            raise RuntimeError("必须先调用 reset() 来初始化环境")
        # 每一步前都先确保后端进程健康可用。
        self.check_process()
        # 执行前恢复运行态，避免在暂停态下 step 无效。
        # self.unpause()
        data = {
            "code": code,
            "programs": programs,
        }
        res = requests.post(
            f"{self.server}/step", json=data, timeout=self.request_timeout
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
    ) -> Tuple[ObsType, Dict[str, Any]]:
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
            res = requests.post(f"{self.server}/stop")
            if res.status_code == 200:
                self.connected = False
        if self.mc_instance:
            self.mc_instance.stop()
        self.mineflayer.stop()
        return not self.connected

    def pause(self):
        """将后端切换到暂停态，并同步本地状态位。"""
        if self.mineflayer.is_running and not self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = True
        return self.server_paused

    def unpause(self):
        """将后端从暂停态切回运行态，并同步本地状态位。"""
        if self.mineflayer.is_running and self.server_paused:
            # 后端使用同一个 /pause 接口做状态切换，再次调用即“恢复”。
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = False
            else:
                print(res.json())
        return self.server_paused
