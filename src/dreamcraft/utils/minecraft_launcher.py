import os
from pathlib import Path
import json
import re

import minecraft_launcher_lib
import sys
from constants import BASE_DIR, LOG_DIR, CACHE_DIR
from subprocess import SubprocessMonitor


class MinecraftInstance:
    """Minecraft 客户端/服务进程封装器。

    该类负责：
    1) 准备 Minecraft 启动命令（含微软账号登录与 token 缓存）；
    2) 通过 `SubprocessMonitor` 启动并监控 Minecraft 进程；
    3) 从日志中提取监听端口，供上层（如 Mineflayer/VoyagerEnv）连接；
    4) 在 bot 退出或进程结束时触发 Mineflayer 停止，避免状态不一致。

    说明：
    - 这里的 "MinecraftInstance" 更像一个“受控运行实例”，不是完整服务器管理器；
    - 它将复杂的登录、命令构造和进程生命周期细节封装起来，供上层直接调用。
    """

    def __init__(
        self,
        client_id,
        redirect_url,
        secret_value,
        version,
        mineflayer,
        log_path="logs",
    ):
        """初始化 Minecraft 实例封装。

        参数说明：
        - client_id/redirect_url/secret_value: 微软 OAuth 登录参数；
        - version: 启动的 Minecraft 版本号（传给 launcher 库）；
        - mineflayer: 外部传入的 Mineflayer 监控对象，用于联动停止；
        - log_path: Minecraft 日志目录。
        """
        # OAuth 与版本信息，后续构造启动命令时使用。
        self.client_id = client_id
        self.redirect_url = redirect_url
        self.secret_value = secret_value
        self.version = version
        self.log_path = log_path

        # Minecraft 默认安装目录（由 minecraft_launcher_lib 判定平台路径）。
        self.mc_dir = minecraft_launcher_lib.utils.get_minecraft_directory()

        # 启动后从日志解析得到监听端口；未启动前为 None。
        self.port = None

        def stop_mineflayer():
            """辅助回调：在 Minecraft 生命周期变化时安全停止 Mineflayer。"""
            print("停止Mineflayer...")
            try:
                mineflayer.stop()
            except Exception as e:
                print(e)

        # 预先生成 Minecraft 启动命令（含登录信息）。
        self.mc_command = self.get_mc_command()

        # 用统一监控器托管 Minecraft 进程：
        # - ready_match: 日志命中后视为服务已监听端口；
        # - callback_match: 检测到 bot 离开事件时，联动停止 Mineflayer；
        # - finished_callback: 进程结束时也执行同样清理。
        self.mc_process = SubprocessMonitor(
            commands=self.mc_command,
            name="minecraft",
            ready_match=r"Started serving on (\d+)",
            log_path=self.log_path,
            callback=stop_mineflayer,
            callback_match=r"\[Server thread/INFO\]: bot left the game",
            finished_callback=stop_mineflayer,
        )

    def get_mineflayer_process(self, server_port):
        """构造 Mineflayer 子进程监控器（当前类中未直接使用，保留为扩展接口）。

        备注：在当前项目中，Mineflayer 通常由 `VoyagerEnv` 单独创建并管理；
        本方法提供了同构创建方式，便于未来将职责收敛到同一对象。
        """
        (LOG_DIR / "mineflayer").mkdir(parents=True, exist_ok=True)
        file_path = Path(__file__).resolve().parent
        return SubprocessMonitor(
            commands=[
                "node",
                BASE_DIR / "lib" / "mineflayer" / "index.js",
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=LOG_DIR / "mineflayer",
        )

    def get_mc_command(self):
        """生成 Minecraft 启动命令。

        执行流程：
        1) 检查本地是否已有 `config.json`（缓存登录 token）；
        2) 若没有，则走一次微软设备登录流程并落盘；
        3) 读取配置并调用 launcher 库生成最终命令列表。

        返回：
        - 可直接传给 `subprocess`/`psutil.Popen` 的命令数组。
        """
        file_path = Path(__file__).resolve().parent

        # 首次运行：没有登录缓存时，触发 OAuth 登录并写入配置。
        if not (CACHE_DIR/'credentials.json').exists():
            (
                login_url,
                state,
                code_verifier,
            ) = minecraft_launcher_lib.microsoft_account.get_secure_login_data(
                self.client_id, self.redirect_url
            )
            print(
                f"请在浏览器中打开 {login_url} 完成登录，并将跳转URL粘贴到下面的输入框中："
            )
            code_url = input()

            try:
                # 校验 state 并从回跳 URL 中解析授权码。
                auth_code = (
                    minecraft_launcher_lib.microsoft_account.parse_auth_code_url(
                        code_url, state
                    )
                )
            except AssertionError:
                print("状态校验失败，登录可能被篡改或中断，请重试。")
                sys.exit(1)
            except KeyError:
                print("授权码解析失败，请确保输入了正确的回跳 URL。")
                sys.exit(1)

            # 用授权码换取账号信息与 access_token。
            login_data = minecraft_launcher_lib.microsoft_account.complete_login(
                self.client_id,
                self.secret_value,
                self.redirect_url,
                auth_code,
                code_verifier,
            )

            # launcher 期望的最小启动参数集合。
            options = {
                "username": login_data["name"],
                "uuid": login_data["id"],
                "token": login_data["access_token"],
            }
            # 持久化到本地，后续复用避免每次都手动登录。
            if not CACHE_DIR.exists():
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR/'credentials.json').write_text(json.dumps(options), encoding="utf-8")
            print(f"登录成功, token缓存至 {CACHE_DIR / 'credentials.json'}")

        # 读取缓存配置，拼装最终可执行命令。
        options = json.loads((CACHE_DIR/'credentials.json').read_text(encoding="utf-8"))
        mc_command = minecraft_launcher_lib.command.get_minecraft_command(
            self.version, self.mc_dir, options
        )

        return mc_command

    def run(self):
        """启动 Minecraft 进程并解析监听端口。"""
        # run() 会阻塞到 ready_match 命中（或启动失败被释放）。
        self.mc_process.run()
        pattern = r"Started serving on (\d+)"

        # ready_line 来自 SubprocessMonitor 捕获的“就绪日志行”。
        match = re.search(pattern, self.mc_process.ready_line)
        if match:
            self.port = int(match.group(1))
            print("捕获到 Minecraft 服务器端口为: ", self.port)
        else:
            # 启动成功但无法提取端口时，直接抛错给上层处理。
            raise RuntimeError("Minecraft 启动成功但未能捕获监听端口，请检查日志确认启动状态。")

    def stop(self):
        """停止 Minecraft 进程。"""
        self.mc_process.stop()

    @property
    def is_running(self):
        """Minecraft 进程是否仍在运行。"""
        return self.mc_process.is_running
