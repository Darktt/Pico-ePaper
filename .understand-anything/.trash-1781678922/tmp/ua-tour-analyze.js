#!/usr/bin/env node
'use strict';

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

// Build node map
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
  .sort((a, b) => b[1] - a[1])
  .slice(0, 20)
  .map(([id, count]) => ({ id, fanIn: count, name: nodeMap[id] ? nodeMap[id].name : id }));

const fanOutRanking = Object.entries(fanOut)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 20)
  .map(([id, count]) => ({ id, fanOut: count, name: nodeMap[id] ? nodeMap[id].name : id }));

// B. Entry Point Candidates
const entryFileNames = new Set([
  'index.ts','index.js','main.ts','main.js','app.ts','app.js',
  'server.ts','server.js','mod.rs','main.go','main.py','main.rs',
  'manage.py','app.py','wsgi.py','asgi.py','run.py','__main__.py',
  'Application.java','Main.java','Program.cs','config.ru','index.php',
  'App.swift','Application.kt','main.cpp','main.c'
]);

const totalNodes = nodes.length;
const fanInValues = Object.values(fanIn).sort((a,b) => a-b);
const fanOutValues = Object.values(fanOut).sort((a,b) => a-b);
const top10pctFanOutThreshold = fanOutValues[Math.floor(fanOutValues.length * 0.9)] || 0;
const bottom25pctFanInThreshold = fanInValues[Math.floor(fanInValues.length * 0.25)] || 0;

const scores = {};
for (const n of nodes) {
  let score = 0;
  if (n.type === 'document') {
    if (n.name === 'README.md' && (!n.filePath || !n.filePath.includes('/'))) {
      score += 5;
    } else if (n.name.endsWith('.md') && (!n.filePath || !n.filePath.includes('/'))) {
      score += 2;
    }
  } else {
    if (entryFileNames.has(n.name)) score += 3;
    const depth = n.filePath ? (n.filePath.match(/\//g) || []).length : 99;
    if (depth <= 1) score += 1;
    if (fanOut[n.id] >= top10pctFanOutThreshold) score += 1;
    if (fanIn[n.id] <= bottom25pctFanInThreshold) score += 1;
  }
  scores[n.id] = score;
}

const entryPointCandidates = Object.entries(scores)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 5)
  .map(([id, score]) => ({
    id,
    score,
    name: nodeMap[id] ? nodeMap[id].name : id,
    summary: nodeMap[id] ? nodeMap[id].summary : ''
  }));

// C. BFS from top code entry point (skip documents)
const topCodeEntry = entryPointCandidates.find(c => {
  const n = nodeMap[c.id];
  return n && n.type !== 'document';
});

const bfsStart = topCodeEntry ? topCodeEntry.id : null;
const bfsOrder = [];
const depthMap = {};
const byDepth = {};

if (bfsStart) {
  // Build adjacency for imports/calls edges
  const adj = {};
  for (const n of nodes) adj[n.id] = [];
  for (const e of edges) {
    if ((e.type === 'imports' || e.type === 'calls') && adj[e.source]) {
      adj[e.source].push(e.target);
    }
  }

  const visited = new Set();
  const queue = [[bfsStart, 0]];
  visited.add(bfsStart);

  while (queue.length > 0) {
    const [current, depth] = queue.shift();
    bfsOrder.push(current);
    depthMap[current] = depth;
    if (!byDepth[depth]) byDepth[depth] = [];
    byDepth[depth].push(current);

    for (const neighbor of (adj[current] || [])) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([neighbor, depth + 1]);
      }
    }
  }
}

// D. Non-Code File Inventory
const nonCodeFiles = {
  documentation: [],
  infrastructure: [],
  data: [],
  config: []
};

for (const n of nodes) {
  if (n.type === 'document') {
    nonCodeFiles.documentation.push({ id: n.id, name: n.name, type: n.type, summary: n.summary });
  } else if (['service','pipeline','resource'].includes(n.type)) {
    nonCodeFiles.infrastructure.push({ id: n.id, name: n.name, type: n.type, summary: n.summary });
  } else if (['table','schema','endpoint'].includes(n.type)) {
    nonCodeFiles.data.push({ id: n.id, name: n.name, type: n.type, summary: n.summary });
  } else if (n.type === 'config') {
    nonCodeFiles.config.push({ id: n.id, name: n.name, type: n.type, summary: n.summary });
  }
}

// E. Tightly Coupled Clusters
const edgeSet = new Set();
const bidir = [];
for (const e of edges) {
  edgeSet.add(`${e.source}-->${e.target}`);
}
const bidirPairs = [];
for (const e of edges) {
  if (edgeSet.has(`${e.target}-->${e.source}`) && e.source < e.target) {
    bidirPairs.push([e.source, e.target]);
  }
}

// Build initial clusters from bidirectional pairs
const clusters = bidirPairs.map(pair => new Set(pair));

// Expand: add nodes connecting to 2+ cluster members
for (const n of nodes) {
  for (const cluster of clusters) {
    if (cluster.has(n.id)) continue;
    let connections = 0;
    for (const member of cluster) {
      if (edgeSet.has(`${n.id}-->${member}`) || edgeSet.has(`${member}-->${n.id}`)) {
        connections++;
      }
    }
    if (connections >= 2) cluster.add(n.id);
  }
}

// Count edges within each cluster
const clusterResults = clusters.map(clusterSet => {
  const members = Array.from(clusterSet);
  let edgeCount = 0;
  for (const e of edges) {
    if (clusterSet.has(e.source) && clusterSet.has(e.target)) edgeCount++;
  }
  return { nodes: members, edgeCount };
}).sort((a, b) => b.edgeCount - a.edgeCount).slice(0, 10);

// F. Layers
const layerInfo = {
  count: layers.length,
  list: layers.map(l => ({ id: l.id, name: l.name, description: l.description }))
};

// G. Node Summary Index
const nodeSummaryIndex = {};
for (const n of nodes) {
  nodeSummaryIndex[n.id] = { name: n.name, type: n.type, summary: n.summary };
}

// Output
const result = {
  scriptCompleted: true,
  entryPointCandidates,
  fanInRanking,
  fanOutRanking,
  bfsTraversal: {
    startNode: bfsStart,
    order: bfsOrder,
    depthMap,
    byDepth
  },
  nonCodeFiles,
  clusters: clusterResults,
  layers: layerInfo,
  nodeSummaryIndex,
  totalNodes: nodes.length,
  totalEdges: edges.length
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  console.log('Done. Output written to', outputPath);
} catch (e) {
  console.error('Failed to write output:', e.message);
  process.exit(1);
}
