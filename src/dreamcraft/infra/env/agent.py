import httpx
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict

from dreamcraft.domain import Observation
from dreamcraft.infra.env.mineflayer_interface import MineflayerServer
from dreamcraft.utils import SubprocessRunner

class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    status: int
    error: Optional[str] = None
    
    @property
    def payload(self) -> Dict[str, Any]:
        return self.model_dump(exclude={'status', 'error'})

class ObservationResponse(ResponseModel):
    observation: Optional[Observation] = None

class StartResponse(ObservationResponse):
    pass

class ExecuteResponse(ObservationResponse):
    pass

class QueryResponse(ResponseModel):
    data: Optional[Dict[str, Any]] = None

class Agent():
    def __init__(
        self,
        settings,
        mineflayer_server: MineflayerServer
    ):
        self.mc_port = settings.mc_port
        self.log_dir = settings.log_dir
        self.mineflayer_port = settings.mineflayer_port
        self.request_timeout = settings.mineflayer_request_timeout
        self.mineflayer_address = f"{settings.mineflayer_host}:{settings.mineflayer_port}"

        # 是否已与后端建立会话连接。
        self.is_connected = False
        self.mineflayer = mineflayer_server

    async def start_mineflayer(self, options) -> Observation: 
        await self.mineflayer.run()
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{self.mineflayer_address}/start",
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
        obs = await self.start_mineflayer(final_options)
        if not obs:
            obs = await self.observe()
        self.is_connected = True
        return obs
    
    async def observe(self) -> Observation:
        if not self.mineflayer.is_running:
            await self.start({"reset": "soft"})
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(f"{self.mineflayer_address}/observe", timeout=self.request_timeout)
                res.raise_for_status()
                return Observation.model_validate_json(res.json())
            except httpx.HTTPError as e:
                raise RuntimeError(
                    f"调用 Minecraft 服务器失败, {str(e)}"
                )
    
    
    async def execute(
        self,
        code: str,
    ) -> dict:
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
                    f"{self.mineflayer_address}/execute", json=data, timeout=self.request_timeout
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
        await self.mineflayer.stop()
        return not self.is_connected

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
