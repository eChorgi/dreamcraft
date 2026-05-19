import { Observation as obs, inject } from "./base.js";
import OnChat from "./onChat.js";
import OnError from "./onError.js";
import { Voxels, BlockRecords } from "./voxels.js";
import Status from "./status.js";
import Inventory from "./inventory.js";
import OnSave from "./onSave.js";
import Chests from "./chests.js";
obs.inject = inject;
// 使用 ESM 的命名导出 (Named Exports)
export {
    obs,
    OnChat,
    OnError,
    Voxels,
    BlockRecords,
    Status,
    Inventory,
    OnSave,
    Chests
};