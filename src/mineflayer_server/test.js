const mineflayer = require('mineflayer')
const { mineflayer: mineflayerViewer } = require('prismarine-viewer')


const bot = mineflayer.createBot({
    host: "localhost", // minecraft server ip
    port: 33333, // minecraft server port
    username: "bot",
    disableChatSigning: true,
    checkTimeoutInterval: 60 * 60 * 1000,
});

bot.on('entityHurt', (entity) => {
  if (entity === bot.entity) {
    console.log('哎哟！我被打了，正在尝试同步位置...')
  }
})

bot.once('spawn', () => {
  mineflayerViewer(bot, { port: 3000, firstPerson: true }) // Start the viewing server on port 3000

  const mcData = require("minecraft-data")(bot.version);
  const possibleLogs = Object.keys(mcData.blocksByName).filter(name => name.includes('log'));
  const tool = require("mineflayer-tool").plugin;
  const collectBlock = require("mineflayer-collectblock").plugin;
  const pvp = require("mineflayer-pvp").plugin;
  const { pathfinder, Movements, goals: { GoalLookAtBlock, GoalPlaceBlock } } = require("mineflayer-pathfinder");
  // const minecraftHawkEye = require("minecrafthawkeye");
  bot.loadPlugin(pathfinder);
  bot.loadPlugin(tool);
  bot.loadPlugin(collectBlock);
  bot.loadPlugin(pvp);
  console.log("当前版本支持的木头名称列表:", possibleLogs);
  // Draw the path followed by the bot
  const path = [bot.entity.position.clone()]
  bot.on('move', () => {
    if (path[path.length - 1].distanceTo(bot.entity.position) > 1) {
      path.push(bot.entity.position.clone())
      bot.viewer.drawLine('path', path)
    }
  })
  // let lastPos = bot.entity.position.clone();
  // setInterval(() => {
  //   if (bot.entity.position.distanceTo(lastPos) < 0.1) {
  //     // 如果正在任务中但位置 2 秒没动，强制中断
  //     console.log("检测到卡顿，强制重置路径...");
  //     bot.pathfinder.setGoal(null);
  //   }
  //   lastPos = bot.entity.position.clone();
  // }, 2000);
})
bot.on('chat', (username, message) => {
  if (username === bot.username) return
  const {
        Movements,
        goals: {
            Goal,
            GoalBlock,
            GoalNear,
            GoalXZ,
            GoalNearXZ,
            GoalY,
            GoalGetToBlock,
            GoalLookAtBlock,
            GoalBreakBlock,
            GoalCompositeAny,
            GoalCompositeAll,
            GoalInvert,
            GoalFollow,
            GoalPlaceBlock,
        },
        pathfinder,
        Move,
        ComputedPath,
        PartiallyComputedPath,
        XZCoordinates,
        XYZCoordinates,
        SafeBlock,
        GoalPlaceBlockOptions,
    } = require("mineflayer-pathfinder");
    const { Vec3 } = require('vec3');
        (async () => {
            const mcData = require("minecraft-data")(bot.version);
        bot.chat("开始：合成工作台并放置");
            const movements = new Movements(bot, mcData);
            bot.pathfinder.setMovements(movements);
        }
    )
});

// 记录错误和被踢出服务器的原因:
bot.on('kicked', console.log)
bot.on('error', console.log)

async function mineOneWoodLog(bot) {
  const mcData = require("minecraft-data")(bot.version);
  bot.chat("正在寻找原木木头以挖掘...");

  // 木头候选（如果周围不止oak_log也能兼容）
  const candidateLogs = [
    "oak_log",
    "birch_log",
    "spruce_log",
    "jungle_log",
    "acacia_log",
    "dark_oak_log",
    "mangrove_log"
  ];

  // 用于计数：最多尝试这些木头类型，最终只挖1个
  for (const logName of candidateLogs) {
    const blockDef = mcData?.blocksByName?.[logName];
    console.log(logName, !!blockDef)
    if (!blockDef) continue;

    // mineBlock 会自动：定位附近方块 -> 寻路 -> 挖掘 -> 收集掉落
    bot.chat(`尝试挖掘：${logName}`);
    try {
      await mineBlock(bot, logName, 2);
      bot.chat("完成！已挖到 1 块木头（原木）。");
      return;
    } catch (e) {
      // 若该类型在附近不可达/不可挖，再尝试下一个
      console.log(`挖掘 ${logName} 失败:`, e);
      bot.chat(`挖掘失败/不可用：${logName}，继续尝试其他原木...`);
    }
  }

  bot.chat("未能在周围找到可挖的原木。");
}



async function mineBlock(bot, name, count = 1) {
    const mcData = require("minecraft-data")(bot.version);
    const blockByName = mcData.blocksByName[name];
    
    if (!blockByName) throw new Error(`找不到方块: ${name}`);

    // 1. 找多少个？就找 count 个！最多加 2-3 个备选就行，别加 1024
    const blocks = bot.findBlocks({
        matching: [blockByName.id],
        maxDistance: 32,
        count: count, 
    });

    if (blocks.length === 0) {
        bot.chat(`附近没找到 ${name}`);
        return;
    }

    // 2. 将坐标转换为方块对象列表
    const targets = blocks.map(pos => bot.blockAt(pos));

    try {
        bot.chat(`准备挖掘 ${targets.length} 个 ${name}...`);
        
        // 3. 直接把 targets 丢给 collect，它内部会自动处理循环挖掘
        // 设置一个超时，防止某个方块卡住导致整条路断掉
        await bot.collectBlock.collect(targets, {
            ignoreNoPath: true,
            count: count
        });

    } catch (e) {
        console.error("挖掘任务中断:", e);
    } finally {
        // 4. 无论成功失败，必须清空目标，否则机器人会滑步
        bot.pathfinder.setGoal(null);
    }

    // bot.save(`${name}_mined`);
}