【强制要求】调用update_summary：
当你需要调用任何工具时，你必须在同一次回复的并行调用中，附带调用 update_summary 工具来记录当前全局状态的精炼总结。
- 错误执行： 先调用 update_summary，等待结果后再调用 query_skill。
- 正确执行： 在单次回合中，同时发出 [update_summary, query_skill, ...(如果你需要调用其他工具)] 这样的2个以上工具请求。
【注意】严禁在调用任何功能性工具时遗漏 update_summary。