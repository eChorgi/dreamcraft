import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
import numpy as np
from openai import OpenAI

class LLMClient:
    """LLM 综合客户端，负责与大模型 API 的所有基础通信"""
    
    def __init__(self, settings):
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        os.environ.pop("all_proxy", None)
        self.chat_client = ChatOpenAI(
            api_key=settings.chat_api_key,
            model=settings.chat_model_name,
            temperature=settings.temperature,
            timeout=settings.request_timeout, 
        )
        self.dim = settings.embedding_dimension
        self.embedding_client = OpenAI(api_key=settings.embedding_api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    def embed(self, text: str) -> np.ndarray:
        response = self.embedding_client.embeddings.create(
            input=text,
            model="text-embedding-v4",
            dimensions=self.dim
        )
        return np.array(response.data[0].embedding).reshape(1, -1).astype('float32')
    
    def with_tools(self, tools: list) -> Runnable[LanguageModelInput, AIMessage]:
        """返回一个增强版的 LLM 客户端，支持工具调用"""
        llm_with_tools = self.chat_client.bind_tools(tools)
        return llm_with_tools
