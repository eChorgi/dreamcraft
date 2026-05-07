import json

from IPython.display import display, Markdown
import re

def ipynb_print(data):
    def _parse_node(node, level=0, layers = None):
        md = ""
        # Markdown 规范：每一层级缩进 4 个空格
        indent = "  " * level  
        if layers is None:
            layers = []
        if isinstance(node, str) and node.startswith('[\n'):
            print("检测到可能的 JSON 字符串，尝试解析...")
        try:
            node = json.loads(node.replace("'", '"')) if isinstance(node, str) else node
        except:
            pass
        
        if isinstance(node, dict):
            for k, v in node.items():
                key_format = f"**<span style='color:#e67e22'>{k}</span>**"
                
                # 遇到列表或字典，递归深入
                if isinstance(v, (dict, list)):
                    md += f"{indent}- {key_format}:\n"
                    md += _parse_node(v, level + 1, layers + [k])
                else:
                    md += _parse_node(v, level, layers + [k])

        elif isinstance(node, list):
            for i, item in enumerate(node):
                if level == 0:
                    # 顶层列表：保持你原本的卡片式三级标题
                    md += f"### <span style='color:#7fb8da; font-weight:normal; font-size:16px'>第 {i + 1} 项</span>\n---\n"
                    # 顶层元素不需要加缩进，直接平铺展开
                    md += _parse_node(item, level)
                    md += "<br>\n"
                else:
                    # 嵌套列表：使用柔和的浅色序号标识
                    md += f"{indent}- <span style='color:#9bbcd2'>*[{i}]*</span>:\n"
                    md += _parse_node(item, level + 1, layers)
        elif hasattr(node, "__dict__"):
            # 获取类的名称，作为装饰性的 Key
            class_name = node.__class__.__name__
            md += f"{indent}- **<span style='color:#e67e22'>Object [{class_name}]</span>**:\n"
            # 递归解析该对象的成员变量
            md += _parse_node(node.__dict__, level + 1, layers + [class_name])     
        else:
            # 递归的尽头：基本数据类型 (字符串、数字、布尔值等)
            key_format = f"<span style='color:#6a8a9f'>**{'.'.join(layers)}**</span>"
            str_node = str(node)
            str_node = re.sub(r'\\+n', r'\n', str_node)  # 处理转义的换行符
            is_multiline = isinstance(node, str) and '\n' in str_node
            if is_multiline:
                # 可收起的多行文本：使用 HTML <details> 标签嵌套
                # <summary> 充当点击触发器，加入 cursor:pointer 提升交互细节
                # key_format = f"**{parent_key}**"
                # 默认展开
                md += f"{indent}- {key_format} <details open><summary style='cursor: pointer;'><span style='color: #6a8a9f;'> 点击展开/收起 </span> </summary>\n\n"
                
                if layers and layers[-1] in ["function", "code"]:
                    # 【核心细节】HTML 标签内嵌 Markdown 代码块时，上方必须留出空行（\n\n），否则高亮会失效
                    fence_indent = "    " * (level + 1)
                    md += f"{fence_indent}```javascript\n"
                    for line in str_node.split('\n'):
                        md += f"{fence_indent}{line}\n"
                    md += f"{fence_indent}```\n\n"
                else:
                    # 多行普通文本：加上引用竖线并对齐缩进
                    for line in str_node.split('\n'):
                        md += f"{indent}    > {line}\n"
                    md += "\n\n"
                # md += f"<summary style='cursor: pointer; display: inline-block;'><span style='color: #6a8a9f; margin-left: 8px;'> 点击展开/收起 </span></summary>\n"
                md += f"{indent}    <span style='color:#9bbcd2'>（共 {len(str_node.splitlines())} 行）</span>\n"
                # 闭合折叠标签
                md += f"{indent}  </details>\n"
            else:
                # 单行文本：紧凑显示
                md += f"{indent}- <span style='color:#6a8a9f; font-size:14px'>{key_format}</span> : <span style='color:#9bbcde'>`{str_node}\n`</span>\n\n"
            
        return md

    # 触发递归并进行最终的原生渲染
    final_md = _parse_node(data)
    display(Markdown(final_md))