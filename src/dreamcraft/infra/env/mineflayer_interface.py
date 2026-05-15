

from dreamcraft.utils import SubprocessRunner

class MineflayerServer:
    def __init__(self):
        self.process = self.create_mineflayer_server(self.mineflayer_path, self.mineflayer_port)

        @property
        def is_running(self):
            return self.process.is_running if self.process else False
        
    def create_mineflayer_server(self, mineflayer_path, server_port):
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


    async def run(self):
        if self.is_running:
            return

        retry = 0
        while not self.is_running:
            print("Mineflayer 未运行，正在启动...")
            await self.process.run()
            if not self.is_running:
                if retry > 3:
                    raise RuntimeError("Mineflayer 启动失败")
                else:
                    continue


    async def stop(self):
        if self.is_running:
            await self.process.stop()