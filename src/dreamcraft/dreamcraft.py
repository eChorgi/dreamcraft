import copy
import json
import os
import time
from typing import Dict

from .bridge import MineflayerBridge


class DreamCraft:
    def __init__(
        self,
        mc_port: int = None,
        azure_login: Dict[str, str] = None,
        server_port: int = 3000,
        openai_api_key: str = None,
        env_wait_ticks: int = 20,
        env_request_timeout: int = 600,
        max_iterations: int = 160,
        reset_placed_if_failed: bool = False,
        action_agent_model_name: str = "gpt-5.4-nano",
        action_agent_temperature: float = 1,
        action_agent_task_max_retries: int = 4,
        action_agent_show_chat_log: bool = True,
        action_agent_show_execution_error: bool = True,
        curriculum_agent_model_name: str = "gpt-5.4-nano",
        curriculum_agent_temperature: float = 1,
        curriculum_agent_qa_model_name: str = "gpt-5-nano",
        curriculum_agent_qa_temperature: float = 1,
        curriculum_agent_warm_up: Dict[str, int] = None,
        curriculum_agent_core_inventory_items: str = r".*_log|.*_planks|stick|crafting_table|furnace"
        r"|cobblestone|dirt|coal|.*_pickaxe|.*_sword|.*_axe",
        curriculum_agent_mode: str = "auto",
        critic_agent_model_name: str = "gpt-5.4-nano",
        critic_agent_temperature: float = 1,
        critic_agent_mode: str = "auto",
        skill_manager_model_name: str = "gpt-5.4-nano",
        skill_manager_temperature: float = 1,
        skill_manager_retrieval_top_k: int = 5,
        openai_api_request_timeout: int = 240,
        max_completion_tokens: int = 50000,
        ckpt_dir: str = "ckpt",
        skill_library_dir: str = None,
        resume: bool = False,
    ):
        """
        Voyager 主控制器。
        -ActionAgent：负责“生成动作代码”
        -CriticAgent：负责“评估任务成功”
        -CurriculumAgent：负责“提出下一任务”
        -SkillManager：负责“技能检索与技能沉淀”

        整体工作方式：
        1) 根据任务与环境观察生成提示词
        2) ActionAgent 产出代码并执行
        3) CriticAgent 评估成功/失败并给出 critique
        4) 用最新事件更新下一轮提示，直到成功或达到重试上限

        :param mc_port: 我的世界游戏内端口
        :param azure_login: 我的世界登录配置
        :param server_port: mineflayer服务端口
        :param openai_api_key: openai api 密钥
        :param env_wait_ticks: 如果您发现某些聊天日志丢失，每个步骤最后将等待多少个刻度，你应该增加这个值
        :param env_request_timeout: 每一步等待多少秒，如果代码执行超过这个时间，python端会终止连接，需要恢复
        :param reset_placed_if_failed: 如果失败是否重置放置的块，对于构建任务很有用
        :param action_agent_model_name: 动作代理模型名称
        :param action_agent_Temperature: 动作代理温度
        :param action_agent_task_max_retries: 失败重试次数
        :paramcurriculum_agent_model_name: 课程代理模型名称
        :param course_agent_Temperature: 课程代理温度
        :param course_agent_qa_model_name: 课程代理 qa 模型名称
        :param course_agent_qa_Temperature: 课程代理质量保证温度
        ：param course_agent_warm_up：信息将显示在课程人类消息中
        如果完成的任务大于字典中的值，可用的键是：
        {
            "context": int,
            "biome": int,
            "time": int,
            "other_blocks": int,
            "nearby_entities": int,
            "health": int,
            "hunger": int,
            "position": int,
            "equipment": int,
            "chests": int,
            "optional_inventory_items": int,
        }
        ：param course_agent_core_inventory_items：仅在可选_inventory_items之前显示库存中的这些项目
        热身时达到
        :param course_agent_mode: "auto" 为自动课程，"manual" 为人工课程
        :paramritic_agent_model_name: 批评者代理模型名称
        :param Criteria_agent_Temperature: 临界代理温度
        :param Criteria_agent_mode: "auto" 用于自动批评家，"manual" 用于人类批评家
        :param Skill_manager_model_name: 技能管理器模型名称
        :param Skill_manager_Temperature: 技能管理器温度
        :param Skill_manager_retrieval_top_k: 每个任务检索多少个技能
        :param openai_api_request_timeout: 等待openai api多少秒
        :param ckpt_dir: 检查点目录
        :param Skill_library_dir: 技能库目录
        :paramresume: 是否从检查点恢复
        """
        # 1) 初始化环境桥接层（Python <-> Mineflayer）。
        self.env = MineflayerBridge(
            mc_port=mc_port,
            azure_login=azure_login,
            server_port=server_port,
            request_timeout=env_request_timeout,
        )
        # 每步结束后等待 tick，可缓解观测日志不完整问题。
        self.env_wait_ticks = env_wait_ticks
        # 构建类任务失败时，是否回滚本轮放置的方块。
        self.reset_placed_if_failed = reset_placed_if_failed
        # learn() 的最大外层迭代次数。
        self.max_iterations = max_iterations
        # 每个任务最多尝试次数（step 次数上限）。
        self.action_agent_task_max_retries = action_agent_task_max_retries

        # 2) 配置模型 API Key（供下游各 Agent 调用）。
        os.environ["OPENAI_API_KEY"] = openai_api_key

        # 3) 初始化四个 Agent。
        self.action_agent = ActionAgent(
            model_name=action_agent_model_name,
            temperature=action_agent_temperature,
            request_timout=openai_api_request_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            chat_log=action_agent_show_chat_log,
            execution_error=action_agent_show_execution_error,
            max_completion_tokens=max_completion_tokens,
        )
        self.curriculum_agent = CurriculumAgent(
            model_name=curriculum_agent_model_name,
            temperature=curriculum_agent_temperature,
            qa_model_name=curriculum_agent_qa_model_name,
            qa_temperature=curriculum_agent_qa_temperature,
            request_timout=openai_api_request_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            mode=curriculum_agent_mode,
            warm_up=curriculum_agent_warm_up,
            core_inventory_items=curriculum_agent_core_inventory_items,
            max_completion_tokens=max_completion_tokens,
        )
        self.critic_agent = CriticAgent(
            model_name=critic_agent_model_name,
            temperature=critic_agent_temperature,
            request_timout=openai_api_request_timeout,
            mode=critic_agent_mode,
            max_completion_tokens=max_completion_tokens,
        )
        self.skill_manager = SkillManager(
            model_name=skill_manager_model_name,
            temperature=skill_manager_temperature,
            retrieval_top_k=skill_manager_retrieval_top_k,
            request_timout=openai_api_request_timeout,
            ckpt_dir=skill_library_dir if skill_library_dir else ckpt_dir,
            resume=True if resume or skill_library_dir else False,
            max_completion_tokens=max_completion_tokens,
        )
        # 记录事件轨迹，用于恢复、回放和统计。
        self.recorder = U.EventRecorder(ckpt_dir=ckpt_dir, resume=resume)
        self.resume = resume

        # 4) rollout 过程中的运行时状态。
        # -1 表示尚未 reset，禁止直接 step。
        self.action_agent_rollout_num_iter = -1
        # 当前任务文本。
        self.task = None
        # 当前任务上下文（外部知识、分解结果等）。
        self.context = ""
        # 当前回合消息：[system_message, human_message]
        self.messages = None
        # 对话历史（三元组：system/human/ai），便于调试与追踪。
        self.conversations = []
        # 最近一次执行得到的环境事件。
        self.last_events = None


    def reset(self, task, context="", reset_env=True):
        """
        为一个新任务初始化 rollout。

        关键动作：
        1) 可选 soft reset 环境
        2) 设置时间与难度并获取首帧观察
        3) 检索技能，构造 ActionAgent 的 system/human message
        """
        self.action_agent_rollout_num_iter = 0
        self.task = task
        self.context = context
        if reset_env:
            self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        # 随着已完成任务增多，提高难度以增加探索有效性。
        difficulty = (
            "easy" if len(self.curriculum_agent.completed_tasks) > 15 else "peaceful"
        )
        # step to peek an observation
        events = self.env.step(
            "bot.chat(`/time set ${getNextTime()}`);\n"
            + f"bot.chat('/difficulty {difficulty}');"
        )
        # 用上下文检索相关技能，注入到 system prompt。
        skills = self.skill_manager.retrieve_skills(query=self.context)
        print(
            f"\033[33mRender Action Agent system message with {len(skills)} skills\033[0m"
        )
        system_message = self.action_agent.render_system_message(skills=skills)
        human_message = self.action_agent.render_human_message(
            events=events, code="", task=self.task, context=context, critique=""
        )
        self.messages = [system_message, human_message]
        print(
            f"\033[32m****Action Agent human message****\n{human_message.content}\033[0m"
        )
        assert len(self.messages) == 2
        self.conversations = []
        return self.messages