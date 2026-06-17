#!/usr/bin/env node
const fs = require('fs');

const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  console.error('Usage: node ua-tour-analyze.js <input.json> <output.json>');
  process.exit(1);
}

let data;
try {
  data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
} catch (e) {
  console.error('Failed to read/parse input:', e.message);
  process.exit(1);
}

const { nodes, edges, layers } = data;

// Build lookup maps
const nodeMap = {};
for (const n of nodes) {
  nodeMap[n.id] = n;
}

// A. Fan-In Ranking
const fanIn = {};
const fanOut = {};
for (const n of nodes) {
  fanIn[n.id] = 0;
  fanOut[n.id] = 0;
}
for (const e of edges) {
  if (fanIn[e.target] !== undefined) fanIn[e.target]++;
  if (fanOut[e.source] !== undefined) fanOut[e.source]++;
}

const fanInRanking = Object.entries(fanIn)
  .map(([id, count]) => ({ id, fanIn: count, name: nodeMap[id]?.name || id }))
  .sort((a, b) => b.fanIn - a.fanIn)
  .slice(0, 20);

// B. Fan-Out Ranking
const fanOutRanking = Object.entries(fanOut)
  .map(([id, count]) => ({ id, fanOut: count, name: nodeMap[id]?.name || id }))
  .sort((a, b) => b.fanOut - a.fanOut)
  .slice(0, 20);

// C. Entry Point Candidates
const totalNodes = nodes.length;
const fanOutValues = Object.values(fanOut).sort((a, b) => a - b);
const fanInValues = Object.values(fanIn).sort((a, b) => a - b);
const top10FanOutThreshold = fanOutValues[Math.floor(totalNodes * 0.9)] || 0;
const bottom25FanInThreshold = fanInValues[Math.floor(totalNodes * 0.25)] || 0;

const entryNamePatterns = [
  'index.ts','index.js','main.ts','main.js','app.ts','app.js','server.ts','server.js',
  'mod.rs','main.go','main.py','main.rs','manage.py','app.py','wsgi.py','asgi.py',
  'run.py','__main__.py','Application.java','Main.java','Program.cs','config.ru',
  'index.php','App.swift','Application.kt','main.cpp','main.c'
];

const entryScores = [];
for (const n of nodes) {
  let score = 0;
  if (n.type === 'document') {
    if (n.name === 'README.md' && (n.filePath === 'README.md' || n.filePath === './README.md')) {
      score += 5;
    } else if (n.name.endsWith('.md') && !n.filePath.includes('/')) {
      score += 2;
    }
  } else {
    // Code/config files
    if (entryNamePatterns.includes(n.name)) score += 3;
    const depth = (n.filePath.match(/\//g) || []).length;
    if (depth <= 1) score += 1;
    if (fanOut[n.id] >= top10FanOutThreshold) score += 1;
    if (fanIn[n.id] <= bottom25FanInThreshold) score += 1;
  }
  if (score > 0) {
    entryScores.push({ id: n.id, score, name: n.name, summary: n.summary || '' });
  }
}
entryScores.sort((a, b) => b.score - a.score);
const entryPointCandidates = entryScores.slice(0, 5);

// D. BFS Traversal from top code entry point
// Skip document nodes for BFS
const topCodeEntry = entryPointCandidates.find(c => nodeMap[c.id]?.type !== 'document');
const bfsStart = topCodeEntry ? topCodeEntry.id : (entryPointCandidates[0]?.id);

const bfsOrder = [];
const depthMap = {};
const bfsVisited = new Set();

if (bfsStart) {
  // Build adjacency for imports/calls edges
  const adj = {};
  for (const n of nodes) adj[n.id] = [];
  for (const e of edges) {
    if ((e.type === 'imports' || e.type === 'calls') && adj[e.source]) {
      adj[e.source].push(e.target);
    }
  }

  const queue = [{ id: bfsStart, depth: 0 }];
  bfsVisited.add(bfsStart);

  while (queue.length > 0) {
    const { id, depth } = queue.shift();
    bfsOrder.push(id);
    depthMap[id] = depth;
    for (const neighbor of (adj[id] || [])) {
      if (!bfsVisited.has(neighbor)) {
        bfsVisited.add(neighbor);
        queue.push({ id: neighbor, depth: depth + 1 });
      }
    }
  }
}

const byDepth = {};
for (const [id, depth] of Object.entries(depthMap)) {
  const key = String(depth);
  if (!byDepth[key]) byDepth[key] = [];
  byDepth[key].push(id);
}

const bfsTraversal = {
  startNode: bfsStart,
  order: bfsOrder,
  depthMap,
  byDepth
};

// E. Non-Code File Inventory
const docTypes = new Set(['document']);
const infraTypes = new Set(['service', 'pipeline', 'resource']);
const dataTypes = new Set(['table', 'schema', 'endpoint']);
const configTypes = new Set(['config']);

const nonCodeFiles = { documentation: [], infrastructure: [], data: [], config: [] };
for (const n of nodes) {
  if (docTypes.has(n.type)) nonCodeFiles.documentation.push({ id: n.id, name: n.name, type: n.type, summary: n.summary || '' });
  else if (infraTypes.has(n.type)) nonCodeFiles.infrastructure.push({ id: n.id, name: n.name, type: n.type, summary: n.summary || '' });
  else if (dataTypes.has(n.type)) nonCodeFiles.data.push({ id: n.id, name: n.name, type: n.type, summary: n.summary || '' });
  else if (configTypes.has(n.type)) nonCodeFiles.config.push({ id: n.id, name: n.name, type: n.type, summary: n.summary || '' });
}

// F. Tightly Coupled Clusters
const edgeSet = new Set();
const bidir = {};
for (const e of edges) {
  const key = `${e.source}|||${e.target}`;
  edgeSet.add(key);
}

// Find bidirectional pairs
const pairs = [];
for (const e of edges) {
  const reverse = `${e.target}|||${e.source}`;
  if (edgeSet.has(reverse) && e.source < e.target) {
    pairs.push([e.source, e.target]);
  }
}

// Build initial clusters from pairs
const clusterMap = {};
for (const [a, b] of pairs) {
  clusterMap[`${a}|||${b}`] = new Set([a, b]);
}

// Expand clusters by adding nodes connecting to 2+ members
const clusters = Object.values(clusterMap);

// Count inter-edges for each cluster
const scoredClusters = clusters.map(cluster => {
  const members = Array.from(cluster);
  let edgeCount = 0;
  for (const m1 of members) {
    for (const m2 of members) {
      if (m1 !== m2 && edgeSet.has(`${m1}|||${m2}`)) edgeCount++;
    }
  }
  return { nodes: members, edgeCount };
}).sort((a, b) => b.edgeCount - a.edgeCount).slice(0, 10);

// G. Layer List
const layerList = {
  count: layers.length,
  list: layers.map(l => ({ id: l.id, name: l.name, description: l.description }))
};

// H. Node Summary Index
const nodeSummaryIndex = {};
for (const n of nodes) {
  nodeSummaryIndex[n.id] = { name: n.name, type: n.type, summary: n.summary || '' };
}

const result = {
  scriptCompleted: true,
  entryPointCandidates,
  fanInRanking,
  fanOutRanking,
  bfsTraversal,
  nonCodeFiles,
  clusters: scoredClusters,
  layers: layerList,
  nodeSummaryIndex,
  totalNodes: nodes.length,
  totalEdges: edges.length
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  console.log('Analysis complete. Output written to', outputPath);
} catch (e) {
  console.error('Failed to write output:', e.message);
  process.exit(1);
}
