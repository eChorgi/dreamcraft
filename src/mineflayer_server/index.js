const fs = require("fs");
const express = require("express");
const bodyParser = require("body-parser");
const mineflayer = require("mineflayer");
const { obs, OnChat, OnError, Voxels, BlockRecords, Status, Inventory, OnSave, Chests } = require("./lib/observation");
const skills = require("./lib/skillLoader");

let bot = null;
const app = express();
// 放宽请求体大小限制，便于传输较长的 program/code 内容。
app.use(bodyParser.json({ limit: "50mb" }));
app.use(bodyParser.urlencoded({ limit: "50mb", extended: false }));

app.post("/start", (req, res) => {
    // 若已有 bot，先优雅断开，避免重复连接同一服务端。
    if (bot) onDisconnect("重启连接");
    bot = null;
    console.log(req.body);
    // 创建 mineflayer bot 并连接到指定端口。
    bot = mineflayer.createBot({
        port: req.body.port, // minecraft server port
        username: "Dream.AI",
        // disableChatSigning: true,
        // checkTimeoutInterval: 60 * 60 * 1000,
    });
    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];
    bot.waitTicks = 20; // 等待 20 个 tick 再返回观测，确保状态稳定。
    bot.once("error", onConnectionFailed);
    bot.on("kicked", onDisconnect);
    bot.on("physicsTick", onTick);
    bot.once("spawn", async () => {
        bot.removeListener("error", onConnectionFailed);
        let itemTicks = 1;
        // hard reset：清空并重建物品/装备状态，确保实验可复现。
        if (req.body.reset === "hard") {
            bot.chat("/clear @s");
            bot.chat("/kill @s");
            const inventory = req.body.inventory ? req.body.inventory : {};
            const equipment = req.body.equipment ? req.body.equipment : [null, null, null, null, null, null];
            for (let key in inventory) {
                bot.chat(`/give @s minecraft:${key} ${inventory[key]}`);
                itemTicks += 1;
            }
            
            const equipmentNames = [
                "armor.head",
                "armor.chest",
                "armor.legs",
                "armor.feet",
                "weapon.mainhand",
                "weapon.offhand",
            ];
            for (let i = 0; i < 6; i++) {
                if (i === 4) continue;
                if (equipment[i]) {
                    bot.chat(
                        `/item replace entity @s ${equipmentNames[i]} with minecraft:${equipment[i]}`
                    );
                    itemTicks += 1;
                }
            }
        }

        // 可选：将 bot 传送到调用方指定坐标。
        if (req.body.position) {
            bot.chat(
                `/tp @s ${req.body.position.x} ${req.body.position.y} ${req.body.position.z}`
            );
        }

        // 动态加载常用插件：寻路、工具选择、采集方块、PVP。
        const { pathfinder } = require("mineflayer-pathfinder");
        const tool = require("mineflayer-tool").plugin;
        const collectBlock = require("mineflayer-collectblock").plugin;
        const pvp = require("mineflayer-pvp").plugin;
        // const minecraftHawkEye = require("minecrafthawkeye");
        bot.loadPlugin(pathfinder);
        bot.loadPlugin(tool);
        bot.loadPlugin(collectBlock);
        bot.loadPlugin(pvp);

        bot.pathfinder.thinkTimeout = 30000; 
        // bot.loadPlugin(minecraftHawkEye);

        obs.inject(bot, [
            OnChat,
            OnError,
            Voxels,
            Status,
            Inventory,
            OnSave,
            Chests,
            BlockRecords,
        ]);
        // // 注入技能函数（供 step 中用户代码直接调用）。
        skills.inject(bot);

        // 可选：随机散布，避免固定出生点导致的场景偏置。
        if (req.body.spread) {
            bot.chat(`/spreadplayers ~ ~ 0 300 under 80 false @s`);
            await bot.waitForTicks(bot.waitTicks);
        }

        // 等待所有开局指令稳定执行后，返回首次观测结果。
        await bot.waitForTicks(bot.waitTicks * itemTicks);
        res.json(bot.observe());
        // res.json({ message: "Success!" });
        // 初始化 tick 计数器并设置常用游戏规则。
        // initCounter(bot);
        // bot.chat("/gamerule keepInventory true");
        // bot.chat("/gamerule doDaylightCycle false");
    });

    // 连接阶段失败：返回 400 并清空 bot。
    function onConnectionFailed(e) {
        console.log(e);
        bot = null;
        res.status(400).json({ error: e });
    }

    // 统一断开逻辑：关闭 viewer、结束连接、释放全局引用。
    function onDisconnect(message) {
        if (bot.viewer) {
            bot.viewer.close();
        }
        bot.end();
        console.log(message);
        bot = null;
    }

    function onTick() {
        bot.globalTickCounter++;
        if (bot.pathfinder.isMoving()) {
            bot.stuckTickCounter++;
            if (bot.stuckTickCounter >= 100) {
                onStuck(1.5);
                bot.stuckTickCounter = 0;
            }
        }
    }
    // 卡死检测：维护长度为 5 的位置窗口，位移不足阈值则视为被卡住。
    function onStuck(posThreshold) {
        const currentPos = bot.entity.position;
        bot.stuckPosList.push(currentPos);

        // Check if the list is full
        if (bot.stuckPosList.length === 5) {
            const oldestPos = bot.stuckPosList[0];
            const posDifference = currentPos.distanceTo(oldestPos);

            if (posDifference < posThreshold) {
                teleportBot(); // execute the function
            }

            // Remove the oldest time from the list
            bot.stuckPosList.shift();
        }
    }

    // 传送解卡：优先传送到附近空气方块，否则向上微调坐标。
    function teleportBot() {
        const blocks = bot.findBlocks({
            matching: (block) => {
                return block.type === 0;
            },
            maxDistance: 1,
            count: 27,
        });

        if (blocks) {
            // console.log(blocks.length);
            const randomIndex = Math.floor(Math.random() * blocks.length);
            const block = blocks[randomIndex];
            bot.chat(`/tp @s ${block.x} ${block.y} ${block.z}`);
        } else {
            bot.chat("/tp @s ~ ~1.25 ~");
        }
    }

});

app.get("/observe", async (req, res) => {
    if (!bot) {
        res.status(400).json({ error: "Bot 没有连接" });
        return;
    }
    res.json(bot.observe());
});

// 执行一步任务：运行外部注入的 code/programs，返回新观测。
app.post("/execute", async (req, res) => {
    // 避免重复响应（异常分支与正常分支都可能尝试返回）。
    let response_sent = false;

    // 兜底异常处理：捕获未处理异常并转为 bot error，再回传观测。
    function otherError(err) {
        console.log("捕获未处理异常:", err);
        bot.emit("error", handleError(err));
        bot.waitForTicks(bot.waitTicks).then(() => {
            if (!response_sent) {
                response_sent = true;
                res.json(bot.observe());
            }
        });
    }

    process.on("uncaughtException", otherError);

    // 兼容项：统一物品/方块别名，降低不同命名导致的执行失败。
    const mcData = require("minecraft-data")(bot.version);
    // mcData.itemsByName["leather_cap"] = mcData.itemsByName["leather_helmet"];
    // mcData.itemsByName["leather_tunic"] = mcData.itemsByName["leather_chestplate"];
    // mcData.itemsByName["leather_pants"] = mcData.itemsByName["leather_leggings"];
    // mcData.itemsByName["lapis_lazuli_ore"] = mcData.itemsByName["lapis_ore"];
    // mcData.blocksByName["lapis_lazuli_ore"] = mcData.blocksByName["lapis_ore"];
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
    const { Vec3 } = require("vec3");
    // 每个 step 都重建 movement 配置，确保路径规划参数与当前状态一致。
    const movements = new Movements(bot, mcData);
    bot.pathfinder.setMovements(movements);

    // 重置卡死检测计数。
    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];

    // 预留失败计数变量（供动态代码使用）。
    let _craftItemFailCount = 0;
    let _killMobFailCount = 0;
    let _mineBlockFailCount = 0;
    let _placeItemFailCount = 0;
    let _smeltItemFailCount = 0;

    // 读取调用方传入的 program（依赖函数）与 code（当前步骤主体）。
    const code = req.body.code;
    // 累积观测用于调试/回放。
    bot.cumulativeObs = [];
    await bot.waitForTicks(bot.waitTicks);
    const r = await evaluateCode(code);
    // 清理兜底异常监听，避免影响后续请求。
    process.off("uncaughtException", otherError);
    if (r !== "success") {
        bot.emit("error", handleError(r));
    }
    // 尝试回收工作台/熔炉等临时资源，减少环境污染。
    // await returnItems();
    // 等待最后一批消息/状态同步后再返回观测。
    await bot.waitForTicks(bot.waitTicks);
    if (!response_sent) {
        response_sent = true;
        res.json(bot.observe());
    }

    async function evaluateCode(code) {
        // 将 programs 与 code 拼接为一个 async IIFE 执行。
        // 这里故意返回字符串/错误对象，交由上层统一处理。
        try {
            await eval("(async () => {" + code + "})()");
            return "success";
        } catch (err) {
            return err;
        }
    }
    function handleError(err) {
        return err.message;
    }
});

//     function handleError(err) {
//         let stack = err.stack;
//         if (!stack) {
//             return err;
//         }
//         console.log(stack);
//         const final_line = stack.split("\n")[1];
//         const regex = /<anonymous>:(\d+):\d+\)/;

//         const programs_length = programs.split("\n").length;
//         let match_line = null;
//         for (const line of stack.split("\n")) {
//             const match = regex.exec(line);
//             if (match) {
//                 const line_num = parseInt(match[1]);
//                 if (line_num >= programs_length) {
//                     match_line = line_num - programs_length;
//                     break;
//                 }
//             }
//         }
//         if (!match_line) {
//             return err.message;
//         }
//         let f_line = final_line.match(
//             /\((?<file>.*):(?<line>\d+):(?<pos>\d+)\)/
//         );
//         if (f_line && f_line.groups && fs.existsSync(f_line.groups.file)) {
//             const { file, line, pos } = f_line.groups;
//             const f = fs.readFileSync(file, "utf8").split("\n");
//             // let filename = file.match(/(?<=node_modules\\)(.*)/)[1];
//             let source = file + `:${line}\n${f[line - 1].trim()}\n `;

//             const code_source =
//                 "at " +
//                 code.split("\n")[match_line - 1].trim() +
//                 " in your code";
//             return source + err.message + "\n" + code_source;
//         } else if (
//             f_line &&
//             f_line.groups &&
//             f_line.groups.file.includes("<anonymous>")
//         ) {
//             const { file, line, pos } = f_line.groups;
//             let source =
//                 "Your code" +
//                 `:${match_line}\n${code.split("\n")[match_line - 1].trim()}\n `;
//             let code_source = "";
//             if (line < programs_length) {
//                 source =
//                     "In your program code: " +
//                     programs.split("\n")[line - 1].trim() +
//                     "\n";
//                 code_source = `at line ${match_line}:${code
//                     .split("\n")
//                     [match_line - 1].trim()} in your code`;
//             }
//             return source + err.message + "\n" + code_source;
//         }
//         return err.message;
//     }
// });
app.get("/test", (req, res) => {
    res.json({ message: "Hello, world!" });
});

const DEFAULT_PORT = 3000;
const PORT = process.argv[2] || DEFAULT_PORT;
app.listen(PORT, () => {
    console.log(`Server started on port ${PORT}`);
});
