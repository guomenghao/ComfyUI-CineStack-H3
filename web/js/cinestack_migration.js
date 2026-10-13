// CineStack legacy workflow migration; no global aliases or upstream node interception.
import { app } from "../../../scripts/app.js";

export const LEGACY_NODE_IDS = {
    "MiniMaxH3Director": "CineStackH3Director",
    "MiniMaxH3DirectorRefine": "CineStackH3DirectorRefine",
    "MiniMaxH3DirectorSelfLift": "CineStackH3DirectorSelfLift",
    "MiniMaxH3DirectorSemanticBridge": "CineStackH3DirectorSemanticBridge",
    "MiniMaxH3DirectorFaceRefine": "CineStackH3DirectorFaceRefine",
    "ComfyMiniMaxH3Director": "CineStackH3Director",
    "MiniMaxH3DirectorConditioning": "CineStackH3DirectorConditioning",
    "MiniMaxH3DirectorPlannerConditioning": "CineStackH3DirectorPlannerConditioning",
    "MiniMaxH3DirectorGroupImageToVideo": "CineStackH3DirectorGroupImageToVideo",
    "MiniMaxH3DirectorGroupReferenceToVideo": "CineStackH3DirectorGroupReferenceToVideo",
    "MiniMaxH3DirectorGroupsCombine": "CineStackH3DirectorGroupsCombine"
};

export function migrateWorkflowInPlace(data, isRegistered = () => false) {
    let changed = 0;
    const migrateNode = (node, key) => {
        const legacy = node?.[key];
        if (!Object.hasOwn(LEGACY_NODE_IDS, legacy) || isRegistered(legacy)) return;
        node[key] = LEGACY_NODE_IDS[legacy];
        changed++;
        if (key === "type") {
            node.properties ??= {};
            Object.assign(node.properties, {"Node name for S&R": node[key],
                cnr_id: "cinestack-h3", ver: "0.1.0", aux_id: "guomenghao/ComfyUI-CineStack-H3"});
        }
    };
    const visit = (graph) => {
        if (!graph || typeof graph !== "object") return;
        for (const node of graph.nodes ?? []) migrateNode(node, "type");
        for (const subgraph of graph.definitions?.subgraphs ?? []) visit(subgraph);
        for (const group of Object.values(graph.extra?.groupNodes ?? {})) visit(group);
    };
    visit(data);
    const prompt = data?.prompt ?? data;
    if (prompt && typeof prompt === "object") {
        for (const node of Object.values(prompt)) migrateNode(node, "class_type");
    }
    return changed;
}

app.registerExtension({
    name: "CineStack.H3.WorkflowMigration",
    beforeConfigureGraph(graphData) {
        // With both plugins installed, leave upstream workflows with upstream.
        const registered = globalThis.LiteGraph?.registered_node_types ?? {};
        const count = migrateWorkflowInPlace(graphData, id => Object.hasOwn(registered, id));
        if (count) console.info(`[CineStack] Migrated ${count} legacy Director nodes in memory.`);
    },
});
