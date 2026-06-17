#!/usr/bin/env node
'use strict';

const fs = require('fs');

const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  console.error('Usage: node ua-arch-analyze.js <input.json> <output.json>');
  process.exit(1);
}

let input;
try {
  input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
} catch (e) {
  console.error('Failed to read input:', e.message);
  process.exit(1);
}

const { fileNodes, importEdges, allEdges } = input;

// ── A. Directory Grouping ──────────────────────────────────────────────────────

// Compute common prefix
function commonPrefix(paths) {
  if (!paths.length) return '';
  const parts = paths.map(p => p.split('/'));
  const minLen = Math.min(...parts.map(p => p.length));
  const prefix = [];
  for (let i = 0; i < minLen - 1; i++) {
    const seg = parts[0][i];
    if (parts.every(p => p[i] === seg)) prefix.push(seg);
    else break;
  }
  return prefix.length ? prefix.join('/') + '/' : '';
}

const allPaths = fileNodes.map(n => n.filePath);
const prefix = commonPrefix(allPaths);

function getGroupKey(filePath) {
  let rel = filePath;
  if (prefix && rel.startsWith(prefix)) rel = rel.slice(prefix.length);
  const parts = rel.split('/');
  if (parts.length === 1) return '__root__';
  return parts[0];
}

const directoryGroups = {};
for (const node of fileNodes) {
  const key = getGroupKey(node.filePath);
  if (!directoryGroups[key]) directoryGroups[key] = [];
  directoryGroups[key].push(node.id);
}

// ── B. Node Type Grouping ──────────────────────────────────────────────────────

const nodeTypeGroups = {};
for (const node of fileNodes) {
  const t = node.type;
  if (!nodeTypeGroups[t]) nodeTypeGroups[t] = [];
  nodeTypeGroups[t].push(node.id);
}

// ── C. Import Adjacency / Fan-in / Fan-out ────────────────────────────────────

const fanOut = {};
const fanIn = {};
for (const node of fileNodes) {
  fanOut[node.id] = 0;
  fanIn[node.id] = 0;
}
for (const edge of importEdges) {
  if (fanOut[edge.source] !== undefined) fanOut[edge.source]++;
  if (fanIn[edge.target] !== undefined) fanIn[edge.target]++;
}

// ── D. Cross-Category Dependency Analysis ─────────────────────────────────────

const nodeTypeById = {};
for (const node of fileNodes) nodeTypeById[node.id] = node.type;

const crossCategoryMap = {};
for (const edge of allEdges) {
  const fromType = nodeTypeById[edge.source];
  const toType = nodeTypeById[edge.target];
  if (!fromType || !toType || fromType === toType) continue;
  const key = `${fromType}|${toType}|${edge.type}`;
  if (!crossCategoryMap[key]) crossCategoryMap[key] = 0;
  crossCategoryMap[key]++;
}
const crossCategoryEdges = Object.entries(crossCategoryMap).map(([key, count]) => {
  const [fromType, toType, edgeType] = key.split('|');
  return { fromType, toType, edgeType, count };
});

// ── E. Inter-Group Import Frequency ───────────────────────────────────────────

const nodeGroupById = {};
for (const node of fileNodes) nodeGroupById[node.id] = getGroupKey(node.filePath);

const interGroupMap = {};
for (const edge of importEdges) {
  const from = nodeGroupById[edge.source];
  const to = nodeGroupById[edge.target];
  if (!from || !to || from === to) continue;
  const key = `${from}|${to}`;
  if (!interGroupMap[key]) interGroupMap[key] = 0;
  interGroupMap[key]++;
}
const interGroupImports = Object.entries(interGroupMap).map(([key, count]) => {
  const [from, to] = key.split('|');
  return { from, to, count };
}).sort((a, b) => b.count - a.count);

// ── F. Intra-Group Import Density ─────────────────────────────────────────────

const intraGroupDensity = {};
for (const group of Object.keys(directoryGroups)) {
  intraGroupDensity[group] = { internalEdges: 0, totalEdges: 0, density: 0 };
}
for (const edge of importEdges) {
  const from = nodeGroupById[edge.source];
  const to = nodeGroupById[edge.target];
  if (from && intraGroupDensity[from]) intraGroupDensity[from].totalEdges++;
  if (from && to && from === to && intraGroupDensity[from]) {
    intraGroupDensity[from].internalEdges++;
  }
}
for (const group of Object.keys(intraGroupDensity)) {
  const g = intraGroupDensity[group];
  g.density = g.totalEdges > 0 ? parseFloat((g.internalEdges / g.totalEdges).toFixed(3)) : 0;
}

// ── G. Directory Pattern Matching ─────────────────────────────────────────────

const dirPatterns = {
  routes: 'api', api: 'api', controllers: 'api', endpoints: 'api', handlers: 'api',
  serializers: 'api', routers: 'api', blueprints: 'api', controller: 'api',
  services: 'service', core: 'service', lib: 'service', domain: 'service', logic: 'service',
  composables: 'service', signals: 'service', mailers: 'service', jobs: 'service', channels: 'service',
  internal: 'service',
  models: 'data', db: 'data', data: 'data', persistence: 'data', repository: 'data',
  entities: 'data', migrations: 'data', sql: 'data', database: 'data', schema: 'data',
  entity: 'data',
  components: 'ui', views: 'ui', pages: 'ui', ui: 'ui', layouts: 'ui', screens: 'ui',
  middleware: 'middleware', plugins: 'middleware', interceptors: 'middleware', guards: 'middleware',
  utils: 'utility', helpers: 'utility', common: 'utility', shared: 'utility', tools: 'utility',
  pkg: 'utility', templatetags: 'utility',
  config: 'config', constants: 'config', env: 'config', settings: 'config',
  management: 'config', commands: 'config',
  '__tests__': 'test', test: 'test', tests: 'test', spec: 'test', specs: 'test',
  types: 'types', interfaces: 'types', schemas: 'types', contracts: 'types', dtos: 'types',
  dto: 'types', request: 'types', response: 'types',
  hooks: 'hooks',
  store: 'state', state: 'state', reducers: 'state', actions: 'state', slices: 'state',
  assets: 'assets', static: 'assets', public: 'assets',
  cmd: 'entry', bin: 'entry',
  docs: 'documentation', documentation: 'documentation', wiki: 'documentation',
  deploy: 'infrastructure', deployment: 'infrastructure', infra: 'infrastructure',
  infrastructure: 'infrastructure', k8s: 'infrastructure', kubernetes: 'infrastructure',
  helm: 'infrastructure', charts: 'infrastructure', terraform: 'infrastructure',
  tf: 'infrastructure', docker: 'infrastructure',
  '.github': 'ci-cd', '.gitlab': 'ci-cd', '.circleci': 'ci-cd',
  writer: 'utility'
};

const patternMatches = {};
for (const group of Object.keys(directoryGroups)) {
  const lower = group.toLowerCase();
  patternMatches[group] = dirPatterns[lower] || 'unknown';
}

// File-level overrides for root group
const filePatterns = [];
for (const node of fileNodes) {
  const fp = node.filePath;
  const name = node.name;
  let match = null;
  if (/\.(test|spec)\.[^.]+$/.test(fp) || /^test_/.test(name) || /_test\.[^.]+$/.test(fp)) match = 'test';
  else if (/\.d\.ts$/.test(fp)) match = 'types';
  else if ((name === 'index.ts' || name === 'index.js' || name === '__init__.py') && fp.split('/').length > 1) match = 'entry';
  else if (name === 'main.py' || name === 'main.go' || name === 'main.rs' || name === 'lib.rs') match = 'entry';
  else if (name === 'manage.py' || name === 'wsgi.py' || name === 'asgi.py' || name === 'config.ru') match = 'entry';
  else if (/^(Cargo\.toml|go\.mod|Gemfile|pom\.xml|build\.gradle|composer\.json|package\.json|.*\.toml)$/.test(name)) match = 'config';
  else if (/^Dockerfile/.test(name) || /^docker-compose/.test(name)) match = 'infrastructure';
  else if (/\.(tf|tfvars)$/.test(fp)) match = 'infrastructure';
  else if (/Makefile$/.test(name)) match = 'infrastructure';
  else if (/\.(sql)$/.test(fp)) match = 'data';
  else if (/\.(graphql|gql|proto)$/.test(fp)) match = 'types';
  else if (/\.(md|rst)$/.test(fp)) match = 'documentation';
  if (match) filePatterns.push({ id: node.id, pattern: match });
}

// ── H. Deployment Topology ────────────────────────────────────────────────────

const infraFiles = fileNodes.filter(n =>
  /^Dockerfile/.test(n.name) || /^docker-compose/.test(n.name) ||
  /\.(tf|tfvars)$/.test(n.filePath) || /Makefile$/.test(n.name) ||
  /\.(yml|yaml)$/.test(n.filePath) && (n.filePath.includes('.github') || n.filePath.includes('.gitlab'))
).map(n => n.filePath);

const deploymentTopology = {
  hasDockerfile: fileNodes.some(n => /^Dockerfile/.test(n.name)),
  hasCompose: fileNodes.some(n => /^docker-compose/.test(n.name)),
  hasK8s: fileNodes.some(n => /k8s|kubernetes|helm/.test(n.filePath)),
  hasTerraform: fileNodes.some(n => /\.(tf|tfvars)$/.test(n.filePath)),
  hasCI: fileNodes.some(n => n.filePath.includes('.github/workflows') || n.filePath.includes('.gitlab-ci')),
  infraFiles
};

// ── I. Data Pipeline Detection ────────────────────────────────────────────────

const dataPipeline = {
  schemaFiles: fileNodes.filter(n => /\.(graphql|gql|proto|sql)$/.test(n.filePath)).map(n => n.filePath),
  migrationFiles: fileNodes.filter(n => /migration/.test(n.filePath)).map(n => n.filePath),
  dataModelFiles: fileNodes.filter(n => n.tags && n.tags.includes('data-model')).map(n => n.filePath),
  apiHandlerFiles: fileNodes.filter(n => n.tags && n.tags.includes('api-handler')).map(n => n.filePath)
};

// ── J. Documentation Coverage ─────────────────────────────────────────────────

const groupsWithDocs = new Set();
for (const node of fileNodes) {
  if (node.type === 'document' || /\.(md|rst)$/.test(node.filePath)) {
    groupsWithDocs.add(getGroupKey(node.filePath));
  }
}
const allGroups = Object.keys(directoryGroups);
const undocumentedGroups = allGroups.filter(g => !groupsWithDocs.has(g));
const docCoverage = {
  groupsWithDocs: groupsWithDocs.size,
  totalGroups: allGroups.length,
  coverageRatio: parseFloat((groupsWithDocs.size / allGroups.length).toFixed(2)),
  undocumentedGroups
};

// ── K. Dependency Direction ────────────────────────────────────────────────────

const pairCounts = {};
for (const edge of importEdges) {
  const from = nodeGroupById[edge.source];
  const to = nodeGroupById[edge.target];
  if (!from || !to || from === to) continue;
  const fwd = `${from}|${to}`;
  const rev = `${to}|${from}`;
  if (!pairCounts[fwd]) pairCounts[fwd] = 0;
  pairCounts[fwd]++;
}
const dependencyDirection = [];
const seen = new Set();
for (const [key, count] of Object.entries(pairCounts)) {
  const [a, b] = key.split('|');
  const revKey = `${b}|${a}`;
  const pairKey = [a, b].sort().join('|');
  if (seen.has(pairKey)) continue;
  seen.add(pairKey);
  const revCount = pairCounts[revKey] || 0;
  if (count > revCount) dependencyDirection.push({ dependent: a, dependsOn: b });
  else if (revCount > count) dependencyDirection.push({ dependent: b, dependsOn: a });
  else dependencyDirection.push({ dependent: a, dependsOn: b, note: 'equal' });
}

// ── File Stats ─────────────────────────────────────────────────────────────────

const filesPerGroup = {};
for (const [g, ids] of Object.entries(directoryGroups)) filesPerGroup[g] = ids.length;

const nodeTypeCounts = {};
for (const [t, ids] of Object.entries(nodeTypeGroups)) nodeTypeCounts[t] = ids.length;

const fileStats = {
  totalFileNodes: fileNodes.length,
  filesPerGroup,
  nodeTypeCounts
};

// ── Output ─────────────────────────────────────────────────────────────────────

const result = {
  scriptCompleted: true,
  directoryGroups,
  nodeTypeGroups,
  crossCategoryEdges,
  interGroupImports,
  intraGroupDensity,
  patternMatches,
  filePatternMatches: filePatterns,
  deploymentTopology,
  dataPipeline,
  docCoverage,
  dependencyDirection,
  fileStats,
  fileFanIn: fanIn,
  fileFanOut: fanOut
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  console.log('Analysis complete. Total nodes:', fileNodes.length);
} catch (e) {
  console.error('Failed to write output:', e.message);
  process.exit(1);
}
