import httpx

from dreamcraft.domain import Observation
from dreamcraft.utils import SubprocessRunner
from dreamcraft.infra.env.azure_instance import AzureInstance


class MinecraftClient():
    def __init__(
        self,
        settings,
        azure_instance: AzureInstance = None,
    ):
        self.azure_instance = azure_instance
        self.mc_port = azure_instance.mc_port if azure_instance else settings.mc_port
        self.mineflayer_server = f"{settings.mineflayer_host}:{settings.mineflayer_port}"
        self.mineflayer_port = settings.mineflayer_port
        self.request_timeout = settings.mineflayer_request_timeout
        self.mineflayer = self.get_mineflayer_process(settings.mineflayer_path, settings.mineflayer_port)
        # 是否至少完成过一次 reset；step 前必须为 True。
        self.has_reset = False
        # 保存最近一次 reset 传给后端的配置，供重连时复用。
        self.reset_options = None
        # 是否已与后端建立会话连接。
        self.connected = False
        # 本地维护的暂停状态镜像，避免重复发送 pause 切换请求。
        self.server_paused = False
        self.log_dir = settings.log_dir

    def get_mineflayer_process(self, mineflayer_path, server_port):
        (self.log_dir / "mineflayer").mkdir(parents=True, exist_ok=True)
        return SubprocessRunner(
            commands=[
                "node",
                str(mineflayer_path),
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=self.log_dir / "mineflayer",
        )

    
    async def _start_azure(self):
        """确保 Minecraft/Mineflayer 进程可用，并在需要时执行后端 start。"""
        # 如果启用了 mc_instance 且当前未运行，则先拉起 Minecraft。
        if self.azure_instance and not self.azure_instance.is_running:
            print("正在启动 Minecraft 服务器...")
            await self.azure_instance.run()
            self.mc_port = self.azure_instance.mc_port
            self.reset_options["port"] = self.azure_instance.mc_port
            print(f"捕获到 Minecraft 服务器端口为: {self.reset_options['port']}")

    async def _start_mineflayer(self, options) -> Observation: 
        retry = 0
        while not self.mineflayer.is_running:
            print("Mineflayer 未运行，正在启动...")
            await self.mineflayer.run()
            if not self.mineflayer.is_running:
                if retry > 3:
                    raise RuntimeError("Mineflayer 启动失败")
                else:
                    continue
            async with httpx.AsyncClient() as client:
                try:
                    res = await client.post(
                        f"{self.mineflayer_server}/start",
                        json=options,
                        timeout=self.request_timeout,
                    )
                    res.raise_for_status()
                    return Observation.model_validate_json(res.json())
                except httpx.HTTPError as e:
                    # start 失败时停止进程，避免进入不一致状态。
                    await self.mineflayer.stop()
                    raise RuntimeError(
                        f"Minecraft 服务器错误, {str(e)}"
                    )
    
    async def start(self, options = {}) -> Observation:
        final_options = {
            "port": self.mc_port,
            "reset": options.get("mode", "hard"),
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }
        await self._start_azure()
        obs = await self._start_mineflayer(final_options)
        if not obs:
            obs = await self.observe()
        self.connected = True
        return obs
    
    async def observe(self) -> Observation:
        if not self.mineflayer.is_running or (self.azure_instance and not self.azure_instance.is_running):
            await self.start({"reset": "soft"})
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(f"{self.mineflayer_server}/observe", timeout=self.request_timeout)
                res.raise_for_status()
                return Observation.model_validate_json(res.json())
            except httpx.HTTPError as e:
                raise RuntimeError(
                    f"调用 Minecraft 服务器失败, {str(e)}"
                )
        # response = requests.get(f"{self.mineflayer_server}/observe", timeout=self.request_timeout)
        # if response.status_code != 200:
        #     raise RuntimeError(f"调用 Minecraft 服务器失败，状态码: {response.status_code}")
        # return Observation.model_validate_json(response.json())
    
    
    async def execute(
        self,
        code: str,
    ) -> Observation:
        """执行代码：发送代码到后端，返回环境观测结果。"""
        data = {
            "code": code
        }
        async with httpx.AsyncClient() as client:
            status = 500
            error_text = None
            observation = None
            try:
                res = await client.post(
                    f"{self.mineflayer_server}/step", json=data, timeout=self.request_timeout
                )
                res.raise_for_status()
                status = res.status_code
                observation = Observation.model_validate_json(res.json())
            except httpx.RequestError as e:
                # 统一处理：无论是网络超时、连接失败，还是 404/500 错误
                status = getattr(e.response, "status_code", 500)
                error_text = str(e)
                if hasattr(e, "response") and e.response:
                    error_text = e.response.text
            return {
                "observation": observation,
                "status": status,
                "error": error_text,
            }
    async def close(self):
        """关闭会话与子进程，释放资源。"""
        if self.azure_instance:
            await self.azure_instance.stop()
        await self.mineflayer.stop()
        return not self.connected

    # def pause(self):
    #     """将后端切换到暂停态，并同步本地状态位。"""
    #     if self.mineflayer.is_running and not self.server_paused:
    #         res = requests.post(f"{self.mineflayer_server}/pause")
    #         if res.status_code == 200:
    #             self.server_paused = True
    #     return self.server_paused

    # def unpause(self):
    #     """将后端从暂停态切回运行态，并同步本地状态位。"""
    #     if self.mineflayer.is_running and self.server_paused:
    #         # 后端使用同一个 /pause 接口做状态切换，再次调用即“恢复”。
    #         res = requests.post(f"{self.mineflayer_server}/pause")
    #         if res.status_code == 200:
    #             self.server_paused = False
    #         else:
    #             print(res.json())
    #     return self.server_paused
