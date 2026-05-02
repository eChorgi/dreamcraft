import numpy as np
from langchain.tools import tool

from dreamcraft.app.protocols import ILLMClient, IWikiRepo, ISkillRepo


class KnowledgeService:
    def __init__(self, wiki: IWikiRepo = None, llm: ILLMClient = None, skill: ISkillRepo = None):
        self.wiki = wiki
        self.llm = llm
        self.skill = skill

    def query_wiki(self, keyword, items=3):
        query_embedding = self.llm.embed(keyword)
        results = self.wiki.search(query_embedding, top_k=items*5)
        
        final = []
        for r in results:
            if len(r["content"]) < 10:  # 简单过滤掉过短的内容
                continue
            final.append(r)
            if len(final) >= items:
                break
        
        return final
    
    def query_skill(self, keyword, items=3):
        query_embedding = self.llm.embed(keyword)
        return self.skill.search(query_embedding, top_k=items)
    