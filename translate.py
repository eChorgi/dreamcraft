import os, glob, re

path = 'data/skill/js/voyager'
files = glob.glob(os.path.join(path, '*.js'))

translations = {
    "throw new Error(`找不到方块: ${name}`)": "throw new Error(`找不到方块: ${name}`)",
    "bot.chat(`${weapon} is not a valid weapon for shooting`)": "bot.chat(`${weapon} 不是有效的射击武器`)",
    "bot.chat(`No ${weapon} in inventory for shooting`)": "bot.chat(`物品栏中没有 ${weapon} 用于射击`)",
    "bot.chat(`No ${target} nearby`)": "bot.chat(`附近没有 ${target}`)",
    "throw new Error(`mobName for killMob must be a string`)": "throw new Error(`killMob 中的 mobName 必须是字符串`)",
    "throw new Error(`timeout for killMob must be a number`)": "throw new Error(`killMob 中的 timeout 必须是数字`)",
    "bot.chat(`No ${mobName} nearby, please explore first`)": "bot.chat(`附近没有 ${mobName}，请先去探索`)",
    "bot.chat(\"chestPosition for getItemFromChest must be a Vec3\")": "bot.chat(\"getItemFromChest 中的 chestPosition 必须是 Vec3 类型\")",
    "bot.chat(`No item named ${name}`)": "bot.chat(`没有名为 ${name} 的物品`)",
    "bot.chat(`I don't see ${name} in this chest`)": "bot.chat(`我没在箱子里看到 ${name}`)",
    "bot.chat(`Not enough ${name} in chest.`)": "bot.chat(`箱子里的 ${name} 数量不足。`)",
    "throw new Error(\"maxTime must be a number\")": "throw new Error(\"maxTime 必须是数字\")",
    "throw new Error(\"callback must be a function\")": "throw new Error(\"callback 必须是一个函数\")",
    "bot.chat(\"Explore success.\")": "bot.chat(\"探索成功。\")",
    "throw new Error(\"direction cannot be 0, 0, 0\")": "throw new Error(\"direction 不能为 0, 0, 0\")",
    "throw new Error(\n            \"direction must be a Vec3 only with value of -1, 0 or 1\"\n        )": "throw new Error(\n            \"direction 必须是一个仅包含 -1、0 或 1 的 Vec3\"\n        )",
    "bot.chat(\"Max exploration time reached\")": "bot.chat(\"已达到最大探索时间\")",
    
    "bot.chat(`No item named ${name}`)": "bot.chat(`找不到物品: ${name}`)",
    "bot.chat(`No ${name} in inventory`)": "bot.chat(`物品栏中没有 ${name}`)",
    "bot.chat(`Not enough ${name} in inventory.`)": "bot.chat(`物品栏中 ${name} 数量不足。`)",
    "throw new Error(\n            \"chestPosition for depositItemIntoChest must be a Vec3\"\n        )": "throw new Error(\n            \"depositItemIntoChest 的 chestPosition 必须是 Vec3\"\n        )",
    "bot.chat(`Killed ${entity.name}!`)": "bot.chat(`已击杀 ${entity.name}！`)",
    "bot.chat(`Shot ${entity.name}!`)": "bot.chat(`已射击 ${entity.name}！`)",
    "throw new Error(`No crafting table nearby`)": "throw new Error(`附近没有工作台`)",
    "bot.chat(`I cannot make ${name} because I need: ${message}`)": "bot.chat(`我无法制作 ${name}，因为我需要: ${message}`)",
    "throw new Error(\n            `No chest at ${chestPosition}, it is ${chestBlock.name}`\n        )": "throw new Error(\n            `在 ${chestPosition} 处没有箱子，那里是 ${chestBlock.name}`\n        )",
    "throw new Error(\"itemName or fuelName for smeltItem must be a string\")": "throw new Error(\"smeltItem 中的 itemName 或 fuelName 必须是字符串\")",
    "throw new Error(\"count for smeltItem must be a number\")": "throw new Error(\"smeltItem 中的 count 必须是数字\")",
    "throw new Error(`No item named ${itemName}`)": "throw new Error(`找不到物品: ${itemName}`)",
    "throw new Error(`No item named ${fuelName}`)": "throw new Error(`找不到物品: ${fuelName}`)",
    "throw new Error(\"No furnace nearby\")": "throw new Error(\"附近没有熔炉\")",
    "bot.chat(`No ${itemName} to smelt in inventory`)": "bot.chat(`物品栏中没有可以烧制的 ${itemName}`)",
    "bot.chat(`No ${fuelName} as fuel in inventory`)": "bot.chat(`物品栏中没有作为燃料的 ${fuelName}`)",
    "throw new Error(`${fuelName} is not a valid fuel`)": "throw new Error(`${fuelName} 不是有效的燃料`)",
    "throw new Error(`${itemName} is not a valid input`)": "throw new Error(`${itemName} 不是有效的输入物`)",
    "bot.chat(`Smelted ${success_count} ${itemName}.`)": "bot.chat(`成功烧制了 ${success_count} 个 ${itemName}。`)",
    "bot.chat(\n            `Failed to smelt ${itemName}, please check the fuel and input.`\n        )": "bot.chat(\n            `烧制 ${itemName} 失败，请检查燃料和输入物。`\n        )",
    "throw new Error(\"name for craftItem must be a string\")": "throw new Error(\"craftItem 中的 name 必须是字符串\")",
    "throw new Error(\"count for craftItem must be a number\")": "throw new Error(\"craftItem 中的 count 必须是数字\")",
    "bot.chat(\"Craft without a crafting table\")": "bot.chat(\"在没有工作台的情况下合成\")",
    "bot.chat(`I can make ${name}`)": "bot.chat(`我可以合成 ${name}`)",
    "bot.chat(`I did the recipe for ${name} ${count} times`)": "bot.chat(`我执行了 ${name} 的配方 ${count} 次`)",
    "bot.chat(`I cannot do the recipe for ${name} ${count} times`)": "bot.chat(`我无法执行 ${name} 的配方 ${count} 次`)"
}

special = [
    ("throw new Error(\n                `killMob failed too many times, make sure you explore before calling killMob`\n            )", "throw new Error(\n                `killMob 失败次数过多，确保在调用 killMob 前进行了探索`\n            )"),
    ("throw new Error(\n                `smeltItem failed too many times, please check the fuel and input.`\n            )", "throw new Error(\n                `smeltItem 失败次数过多，请检查燃料和输入物。`\n            )"),
    ("throw new Error(\n                \"craftItem failed too many times, check chat log to see what happened\"\n            )", "throw new Error(\n                \"craftItem 失败次数过多，请查看聊天日志以了解原因\"\n            )"),
]


for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    new_content = content
    for old, new in translations.items():
        if old in new_content:
            new_content = new_content.replace(old, new)
            
    for old, new in special:
        if old in new_content:
            new_content = new_content.replace(old, new)
            
    if "`/tp ${chestPosition.x} ${chestPosition.y} ${chestPosition.z}`" not in new_content:
        # Ignore
        pass

    with open(f, 'w', encoding='utf-8') as file:
        file.write(new_content)

print("Done")

