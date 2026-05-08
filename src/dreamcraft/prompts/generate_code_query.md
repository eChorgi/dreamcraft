## 当前目标描述
{target}

## 当前状态快照
{snapshot}

## 额外总结参考
{reason}

## 任务详情
请你根据wiki知识和当前掌握的skill(即函数)编写可以完成目标的 JavaScript 异步脚本与功能函数
- 你需要编写一段脚本, 必须将其中的复杂, 可复用的逻辑提炼成函数再进行调用, 如果是脚本请直接顶格写, 表示直接运行, 函数则以async function开头编写, 禁止使用变量声明函数

## 常用skill(函数)提示
- new Vec3(x, y, z); //任何位置对象必须是一个 Vec3 实例对象，而不能是普通的 JavaScript 对象（如 {x, y, z}）
- bot.isABed(bedBlock)
- bot.blockAt(position)
- await exploreUntil(bot, direction, maxDistance, callback)
- await mineBlock(bot, name, count)
- await craftItem(bot, name, count)
- await smeltItem(bot, name count)
- await placeItem(bot, name, position)
- await killMob(bot, name, timeout)
- await bot.equip(item, destination);
- await bot.consume();
- await bot.fish();
- await bot.sleep(bedBlock);
- await bot.activateBlock(block);
- await bot.lookAt(position);
- await bot.activateItem();
- await bot.useOn(entity);

## 注意
1. 你的函数将被复用于构建更复杂的函数。因此，你应该使其通用且可重用。你不应对物品栏做出强烈假设（因为它可能在稍后时间被更改），因此你应该在使用所需物品前始终检查是否拥有它们。如果没有，你应该首先收集所需物品并重用上述实用程序。
2. 调用 `bot.chat` 并且用中文来显示中间进度。
3. 不要编写无限循环或递归函数。
4. 不要使用 `bot.on` 或 `bot.once` 来注册事件监听器。你绝对不需要它们。
5. 以有意义的方式命名你的函数(可以从名称推断出功能)

## 答案示范
【Final Answer】
await mineWoodLogs(bot, 5);
async function mineWoodLogs(bot, count) {{
  bot.chat("正在寻找原木");
  const candidateLogNames = ["oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log", "mangrove_log"];
  let mined = false;
  for (const name of candidateLogNames) {{
    const blockDef = mcData.blocksByName[name];
    if (!blockDef) continue;
    const found = bot.findBlock({{
      matching: blockDef.id,
      maxDistance: 32
    }});
    if (found) {{
      await bot.chat(`正在挖掘 ${{name}}...`);
      await mineBlock(bot, name, count);
      mined = true;
      break;
    }}
  }}
  if (!mined) {{
    bot.chat("无法在周围32格内找到原木");
  }} else {{
    bot.chat("完成! 已挖掘一个原木");
  }}
}}