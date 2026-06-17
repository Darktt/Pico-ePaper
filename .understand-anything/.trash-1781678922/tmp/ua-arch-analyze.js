#!/usr/bin/env node
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
  console.error('Failed to parse input JSON:', e.message);
  process.exit(1);
}

const { fileNodes, importEdges, allEdges } = input;

// A. Directory Grouping
function commonPrefix(paths) {
  if (!paths.length) return '';
  const parts = paths[0].split('/');
  let prefix = [];
  for (let i = 0; i < parts.length - 1; i++) {
    if (paths.every(p => p.split('/')[i] === parts[i])) {
      prefix.push(parts[i]);
    } else break;
  }
  return prefix.length ? prefix.join('/') + '/' : '';
}

const allPaths = fileNodes.map(n => n.filePath);
const prefix = commonPrefix(allPaths);

const directoryGroups = {};
for (const node of fileNodes) {
  const stripped = node.filePath.startsWith(prefix) ? node.filePath.slice(prefix.length) : node.filePath;
  const parts = stripped.split('/');
  const group = parts.length > 1 ? parts[0] : 'root';
  if (!directoryGroups[group]) directoryGroups[group] = [];
  directoryGroups[group].push(node.id);
}

// B. Node Type Grouping
const nodeTypeGroups = {};
for (const node of fileNodes) {
  const t = node.type || 'file';
  if (!nodeTypeGroups[t]) nodeTypeGroups[t] = [];
  nodeTypeGroups[t].push(node.id);
}

// C. Import adjacency
const fanOut = {};
const fanIn = {};
for (const node of fileNodes) { fanOut[node.id] = 0; fanIn[node.id] = 0; }

for (const edge of importEdges) {
  if (fanOut[edge.source] !== undefined) fanOut[edge.source]++;
  if (fanIn[edge.target] !== undefined) fanIn[edge.target]++;
}

// D. Cross-category dependency analysis
const crossCategoryMap = {};
for (const edge of allEdges) {
  const srcNode = fileNodes.find(n => n.id === edge.source);
  const tgtNode = fileNodes.find(n => n.id === edge.target);
  if (!srcNode || !tgtNode) continue;
  const key = `${srcNode.type}->${tgtNode.type}:${edge.type}`;
  crossCategoryMap[key] = (crossCategoryMap[key] || 0) + 1;
}
const crossCategoryEdges = Object.entries(crossCategoryMap).map(([key, count]) => {
  const [types, edgeType] = key.split(':');
  const [fromType, toType] = types.split('->');
  return { fromType, toType, edgeType, count };
});

// Helper: get group for a node id
function getGroup(nodeId) {
  for (const [g, ids] of Object.entries(directoryGroups)) {
    if (ids.includes(nodeId)) return g;
  }
  return null;
}

// E. Inter-group import frequency
const interGroupMap = {};
for (const edge of importEdges) {
  const fromGroup = getGroup(edge.source);
  const toGroup = getGroup(edge.target);
  if (!fromGroup || !toGroup || fromGroup === toGroup) continue;
  const key = `${fromGroup}->${toGroup}`;
  interGroupMap[key] = (interGroupMap[key] || 0) + 1;
}
const interGroupImports = Object.entries(interGroupMap).map(([key, count]) => {
  const [from, to] = key.split('->');
  return { from, to, count };
}).sort((a, b) => b.count - a.count);

// F. Intra-group import density
const intraGroupDensity = {};
for (const group of Object.keys(directoryGroups)) {
  const groupIds = new Set(directoryGroups[group]);
  let internalEdges = 0;
  let totalEdges = 0;
  for (const edge of importEdges) {
    const srcInGroup = groupIds.has(edge.source);
    const tgtInGroup = groupIds.has(edge.target);
    if (srcInGroup || tgtInGroup) totalEdges++;
    if (srcInGroup && tgtInGroup) internalEdges++;
  }
  intraGroupDensity[group] = {
    internalEdges,
    totalEdges,
    density: totalEdges > 0 ? Math.round((internalEdges / totalEdges) * 100) / 100 : 0
  };
}

// G. Directory pattern matching
const dirPatterns = {
  routes: 'api', api: 'api', controllers: 'api', endpoints: 'api', handlers: 'api',
  serializers: 'api', blueprints: 'api', routers: 'api', controller: 'api',
  services: 'service', core: 'service', lib: 'utility', domain: 'service', logic: 'service',
  composables: 'service', mailers: 'service', jobs: 'service', channels: 'service',
  signals: 'service', internal: 'service',
  models: 'data', db: 'data', data: 'data', persistence: 'data', repository: 'data',
  entities: 'data', migrations: 'data', sql: 'data', database: 'data', schema: 'data',
  entity: 'data',
  components: 'ui', views: 'ui', pages: 'ui', ui: 'ui', layouts: 'ui', screens: 'ui',
  middleware: 'middleware', plugins: 'middleware', interceptors: 'middleware', guards: 'middleware',
  utils: 'utility', helpers: 'utility', common: 'utility', shared: 'utility', tools: 'utility',
  pkg: 'utility', templatetags: 'utility',
  config: 'config', constants: 'config', env: 'config', settings: 'config',
  management: 'config', commands: 'config',
  __tests__: 'test', test: 'test', tests: 'test', spec: 'test', specs: 'test',
  types: 'types', interfaces: 'types', schemas: 'types', contracts: 'types', dtos: 'types',
  dto: 'types', request: 'types', response: 'types',
  hooks: 'hooks',
  store: 'state', state: 'state', reducers: 'state', actions: 'state', slices: 'state',
  assets: 'assets', static: 'assets', public: 'assets',
  docs: 'documentation', documentation: 'documentation', wiki: 'documentation',
  deploy: 'infrastructure', deployment: 'infrastructure', infra: 'infrastructure',
  infrastructure: 'infrastructure', k8s: 'infrastructure', kubernetes: 'infrastructure',
  helm: 'infrastructure', charts: 'infrastructure', terraform: 'infrastructure',
  tf: 'infrastructure', docker: 'infrastructure',
  '.github': 'ci-cd', '.gitlab': 'ci-cd', '.circleci': 'ci-cd',
  bin: 'entry', cmd: 'entry',
  display: 'ui', writer: 'utility'
};

const patternMatches = {};
for (const group of Object.keys(directoryGroups)) {
  patternMatches[group] = dirPatterns[group.toLowerCase()] || 'unknown';
}

// Check file-level patterns
const filePatternOverrides = {};
for (const node of fileNodes) {
  const fp = node.filePath;
  const name = node.name;
  if (/\.(test|spec)\.[^.]+$/.test(fp) || /^test_/.test(name) || /_test\.[^.]+$/.test(name) ||
      /Test\.[^.]+$/.test(name) || /_spec\.[^.]+$/.test(name) || /Tests\.[^.]+$/.test(name)) {
    filePatternOverrides[node.id] = 'test';
  } else if (/\.d\.ts$/.test(fp)) {
    filePatternOverrides[node.id] = 'types';
  } else if (/\/(index\.(ts|js)|__init__\.py)$/.test(fp)) {
    filePatternOverrides[node.id] = 'entry';
  } else if (/\/manage\.py$/.test(fp) || /^manage\.py$/.test(fp)) {
    filePatternOverrides[node.id] = 'entry';
  } else if (/\/(wsgi|asgi)\.py$/.test(fp)) {
    filePatternOverrides[node.id] = 'config';
  } else if (/\/(main\.go)$/.test(fp) && /^cmd\//.test(fp)) {
    filePatternOverrides[node.id] = 'entry';
  } else if (/\/(main\.rs|lib\.rs)$/.test(fp)) {
    filePatternOverrides[node.id] = 'entry';
  } else if (/\/(Application\.java|Program\.cs)$/.test(fp)) {
    filePatternOverrides[node.id] = 'entry';
  } else if (/Dockerfile.*/.test(name) || /docker-compose.*/.test(name)) {
    filePatternOverrides[node.id] = 'infrastructure';
  } else if (/\.(tf|tfvars)$/.test(fp)) {
    filePatternOverrides[node.id] = 'infrastructure';
  } else if (/\.(md|rst)$/.test(fp)) {
    filePatternOverrides[node.id] = 'documentation';
  } else if (/\.(graphql|gql|proto)$/.test(fp)) {
    filePatternOverrides[node.id] = 'types';
  } else if (/\.sql$/.test(fp)) {
    filePatternOverrides[node.id] = 'data';
  } else if (/Makefile$/.test(fp)) {
    filePatternOverrides[node.id] = 'infrastructure';
  } else if (/(Cargo\.toml|go\.mod|Gemfile|pom\.xml|build\.gradle|composer\.json)$/.test(fp)) {
    filePatternOverrides[node.id] = 'config';
  }
}

// H. Deployment topology
const infraKeywords = ['Dockerfile', 'docker-compose', '.tf', '.tfvars', 'k8s', 'kubernetes', '.github/workflows', '.gitlab-ci', 'Jenkinsfile', 'Makefile'];
const infraFiles = fileNodes.filter(n => infraKeywords.some(k => n.filePath.includes(k))).map(n => n.filePath);
const deploymentTopology = {
  hasDockerfile: fileNodes.some(n => /Dockerfile/.test(n.name)),
  hasCompose: fileNodes.some(n => /docker-compose/.test(n.name)),
  hasK8s: fileNodes.some(n => /k8s|kubernetes/.test(n.filePath)),
  hasTerraform: fileNodes.some(n => /\.tf$/.test(n.filePath)),
  hasCI: fileNodes.some(n => /\.github\/workflows|\.gitlab-ci|Jenkinsfile/.test(n.filePath)),
  infraFiles
};

// I. Data pipeline detection
const schemaFiles = fileNodes.filter(n => /\.(graphql|gql|proto|prisma|sql)$/.test(n.filePath) || n.tags.includes('schema')).map(n => n.filePath);
const migrationFiles = fileNodes.filter(n => /migration/i.test(n.filePath)).map(n => n.filePath);
const dataModelFiles = fileNodes.filter(n => n.tags.includes('model') || /models?\//.test(n.filePath)).map(n => n.filePath);
const apiHandlerFiles = fileNodes.filter(n => n.tags.includes('api-handler')).map(n => n.filePath);
const dataPipeline = { schemaFiles, migrationFiles, dataModelFiles, apiHandlerFiles };

// J. Documentation coverage
const docNodes = fileNodes.filter(n => n.type === 'document' || /\.(md|rst)$/.test(n.filePath));
const groupsWithDocs = new Set();
for (const doc of docNodes) {
  const group = getGroup(doc.id);
  if (group) groupsWithDocs.add(group);
}
const totalGroups = Object.keys(directoryGroups).length;
const undocumentedGroups = Object.keys(directoryGroups).filter(g => !groupsWithDocs.has(g));
const docCoverage = {
  groupsWithDocs: groupsWithDocs.size,
  totalGroups,
  coverageRatio: Math.round((groupsWithDocs.size / totalGroups) * 100) / 100,
  undocumentedGroups
};

// K. Dependency direction
const dependencyDirection = interGroupImports
  .filter(e => e.count > 0)
  .map(e => ({ dependent: e.from, dependsOn: e.to }));

// File stats
const filesPerGroup = {};
for (const [g, ids] of Object.entries(directoryGroups)) filesPerGroup[g] = ids.length;
const nodeTypeCounts = {};
for (const [t, ids] of Object.entries(nodeTypeGroups)) nodeTypeCounts[t] = ids.length;

const results = {
  scriptCompleted: true,
  directoryGroups,
  nodeTypeGroups,
  crossCategoryEdges,
  interGroupImports,
  intraGroupDensity,
  patternMatches,
  filePatternOverrides,
  deploymentTopology,
  dataPipeline,
  docCoverage,
  dependencyDirection,
  fileStats: {
    totalFileNodes: fileNodes.length,
    filesPerGroup,
    nodeTypeCounts
  },
  fileFanIn: fanIn,
  fileFanOut: fanOut
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log('Analysis complete. Results written to', outputPath);
  process.exit(0);
} catch (e) {
  console.error('Failed to write output:', e.message);
  process.exit(1);
}
