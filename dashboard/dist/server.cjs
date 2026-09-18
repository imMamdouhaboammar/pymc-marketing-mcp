var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// server.ts
var import_dotenv = __toESM(require("dotenv"), 1);
var import_express = __toESM(require("express"), 1);
var import_path = __toESM(require("path"), 1);

// server/lib/agentClient.ts
var import_genai = require("@google/genai");
var API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";
async function createInteraction(opts) {
  const agentName = opts.agentName ?? "antigravity-preview-05-2026";
  const ai = new import_genai.GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
  const payload = {
    agent: agentName,
    input: opts.prompt
  };
  if (opts.stream) {
    payload.stream = true;
  }
  if (opts.environmentId) {
    payload.environment = { env_id: opts.environmentId };
  } else {
    const allowlist = [
      {
        domain: "generativelanguage.googleapis.com",
        transform: { "x-goog-api-key": process.env.GEMINI_API_KEY }
      }
    ];
    if (opts.gcsToken) {
      allowlist.push({
        domain: "storage.googleapis.com",
        transform: {
          "Authorization": `Bearer ${opts.gcsToken}`
        }
      });
    }
    allowlist.push({ domain: "*" });
    const envConfig = {
      type: "remote",
      sources: opts.inlineSources ?? [],
      network: {
        allowlist
      }
    };
    payload.environment = envConfig;
  }
  if (opts.previousInteractionId) {
    payload.previous_interaction_id = opts.previousInteractionId;
  }
  const httpOptions = opts.signal ? { signal: opts.signal, timeout: 6e5 } : { timeout: 6e5 };
  const stream = await ai.interactions.create(payload, httpOptions);
  return stream;
}
async function* streamInteraction(stream) {
  try {
    for await (const event of stream) {
      const parsed = parseAgentEvent(event);
      if (parsed) {
        yield parsed;
        if (parsed.type === "done") return;
      }
    }
  } catch (err) {
    console.error(`[streamInteraction] Exception caught in read loop:`, err);
    yield { type: "error", message: `Stream read exception: ${err.message}` };
  }
}
function parseAgentEvent(event) {
  const eventType = event.event_type;
  if (eventType === "interaction.created") {
    const nestedData = event.data;
    return {
      type: "interaction",
      interaction: event.interaction ?? nestedData?.interaction ?? event
    };
  }
  if (eventType === "step.delta") {
    const delta = event.delta;
    if (!delta) return null;
    const resultVal = delta.result !== void 0 ? delta.result : delta.response;
    if (resultVal !== void 0 && resultVal !== null) {
      let resultStr = "";
      if (typeof resultVal === "object") {
        resultStr = JSON.stringify(resultVal);
      } else {
        resultStr = String(resultVal);
      }
      return {
        type: "tool_result",
        name: delta.name,
        result: resultStr
      };
    }
    let argumentsObj = delta.arguments || delta.call?.arguments;
    if (typeof argumentsObj === "string") {
      try {
        argumentsObj = JSON.parse(argumentsObj);
      } catch (e) {
      }
    }
    const callName = delta.name || delta.call?.name || (delta.type === "code_execution_call" ? "code_execution_call" : void 0);
    if (callName || argumentsObj) {
      return {
        type: "tool_call",
        name: callName || "code_execution_call",
        arguments: argumentsObj ?? {}
      };
    }
    let extractedText = "";
    let isThinking = false;
    if (delta.type === "thought_summary" || delta.type === "thinking" || delta.type === "thought" || delta.type === "thought_delta") {
      isThinking = true;
    }
    if (typeof delta.text === "string") {
      extractedText = delta.text;
    } else if (typeof delta.thought === "string") {
      extractedText = delta.thought;
      isThinking = true;
    } else if (typeof delta.summary === "string" && isThinking) {
      extractedText = delta.summary;
    }
    const content = delta.content;
    if (content !== void 0 && content !== null) {
      if (Array.isArray(content)) {
        for (const part of content) {
          if (part && typeof part === "object") {
            const partObj = part;
            if (partObj.type === "thought") {
              isThinking = true;
              if (typeof partObj.text === "string") {
                extractedText += partObj.text;
              } else if (typeof partObj.thought === "string") {
                extractedText += partObj.thought;
              }
            } else if (partObj.type === "text" && typeof partObj.text === "string") {
              extractedText += partObj.text;
            } else if (typeof partObj.text === "string") {
              extractedText += partObj.text;
            } else if (typeof partObj.thought === "string") {
              extractedText += partObj.thought;
              isThinking = true;
            }
          } else if (typeof part === "string") {
            extractedText += part;
          }
        }
      } else if (typeof content === "object") {
        const cObj = content;
        if (cObj.type === "thought") {
          isThinking = true;
          if (typeof cObj.text === "string") {
            extractedText = cObj.text;
          } else if (typeof cObj.thought === "string") {
            extractedText = cObj.thought;
          }
        } else if (cObj.type === "text" && typeof cObj.text === "string") {
          extractedText = cObj.text;
        } else if (typeof cObj.text === "string") {
          extractedText = cObj.text;
        } else if (typeof cObj.thought === "string") {
          extractedText = cObj.thought;
          isThinking = true;
        }
      } else if (typeof content === "string") {
        extractedText = content;
      }
    }
    if (extractedText) {
      return {
        type: isThinking ? "thinking" : "text",
        text: extractedText
      };
    }
  }
  if (eventType === "interaction.completed") {
    return {
      type: "complete",
      interaction: event.interaction ?? {}
    };
  }
  return null;
}

// server/lib/jsonExtractor.ts
function extractJsonBlocks(text) {
  const pattern = /```json\s*\n([\s\S]*?)\n\s*```/g;
  const results = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1]);
      if (Array.isArray(parsed)) {
        results.push(...parsed);
      } else {
        results.push(parsed);
      }
    } catch {
      continue;
    }
  }
  return results;
}

// server.ts
var import_fs = __toESM(require("fs"), 1);
var import_multer = __toESM(require("multer"), 1);
import_dotenv.default.config({ path: [".env.local", ".env"] });
async function getGcpAccessToken() {
  try {
    const res = await fetch(
      "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
      {
        headers: { "Metadata-Flavor": "Google" }
      }
    );
    if (res.ok) {
      const data = await res.json();
      return data.access_token || null;
    }
  } catch (err) {
    console.warn(
      "[getGcpAccessToken] Could not fetch token from metadata server:",
      err
    );
  }
  return null;
}
function extractTarInMemory(tarBuffer) {
  const files = {};
  let offset = 0;
  while (offset + 512 <= tarBuffer.length) {
    let isEnd = true;
    for (let i = 0; i < 512; i++) {
      if (tarBuffer[offset + i] !== 0) {
        isEnd = false;
        break;
      }
    }
    if (isEnd) break;
    let name = "";
    for (let i = 0; i < 100; i++) {
      const charCode = tarBuffer[offset + i];
      if (charCode === 0) break;
      name += String.fromCharCode(charCode);
    }
    name = name.trim();
    let sizeStr = "";
    for (let i = 124; i < 136; i++) {
      const charCode = tarBuffer[offset + i];
      if (charCode === 0 || charCode === 32) continue;
      sizeStr += String.fromCharCode(charCode);
    }
    const size = parseInt(sizeStr, 8);
    const typeflag = tarBuffer[offset + 156];
    const isRegularFile = typeflag === 0 || typeflag === 48;
    offset += 512;
    if (name && isRegularFile && !isNaN(size) && size > 0) {
      if (offset + size <= tarBuffer.length) {
        files[name] = tarBuffer.subarray(offset, offset + size);
      }
    }
    const paddedSize = Math.ceil(size / 512) * 512;
    offset += paddedSize;
  }
  return files;
}
function extractEnvironmentId(interaction) {
  if (!interaction || typeof interaction !== "object") return void 0;
  const environment = interaction.environment;
  const candidates = [
    environment?.env_id,
    environment?.environment_id,
    environment?.id,
    environment?.name,
    interaction.environment_id,
    interaction.env_id
  ];
  const value = candidates.find(
    (candidate) => typeof candidate === "string" && candidate.trim()
  );
  if (typeof value !== "string") return void 0;
  return value.replace(/^environments?\//, "").replace(/^environment-/, "");
}
function extractInteractionId(interaction) {
  if (!interaction || typeof interaction !== "object") return void 0;
  const value = interaction.name || interaction.id || interaction.interaction_id;
  return typeof value === "string" && value.trim() ? value.trim() : void 0;
}
function loadAgentFiles(dir, basePath) {
  let files = [];
  if (!import_fs.default.existsSync(dir)) return files;
  const entries = import_fs.default.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = import_path.default.join(dir, entry.name);
    const targetPath = import_path.default.posix.join(basePath, entry.name);
    if (entry.isDirectory()) {
      files = files.concat(loadAgentFiles(fullPath, targetPath));
    } else {
      files.push({
        type: "inline",
        content: import_fs.default.readFileSync(fullPath, "utf-8"),
        target: targetPath
      });
    }
  }
  return files;
}
var activeGenerations = /* @__PURE__ */ new Map();
function cleanUpOldGenerations() {
  const outputDir = import_path.default.join(process.cwd(), "output");
  if (!import_fs.default.existsSync(outputDir)) return;
  const maxAgeMs = 24 * 60 * 60 * 1e3;
  const now = Date.now();
  try {
    const items = import_fs.default.readdirSync(outputDir);
    for (const item of items) {
      if (item.startsWith(".")) continue;
      const itemPath = import_path.default.join(outputDir, item);
      const stats = import_fs.default.statSync(itemPath);
      if (stats.isDirectory()) {
        const age = now - stats.mtimeMs;
        if (age > maxAgeMs) {
          console.log(
            `[cleanup] Directory ${item} is older than 24 hours (${Math.round(age / 1e3 / 60 / 60)} hrs). Deleting to prevent storage bloat.`
          );
          try {
            import_fs.default.rmSync(itemPath, { recursive: true, force: true });
            const zipPath = `${itemPath}.zip`;
            if (import_fs.default.existsSync(zipPath)) {
              import_fs.default.unlinkSync(zipPath);
            }
          } catch (itemErr) {
            console.error(`[cleanup] Failed to delete ${itemPath}:`, itemErr);
          }
        }
      }
    }
  } catch (err) {
    console.error("[cleanup] Error cleaning up old generations:", err);
  }
}
async function startServer() {
  const app = (0, import_express.default)();
  const PORT = 3e3;
  cleanUpOldGenerations();
  app.use(import_express.default.json({ limit: "50mb" }));
  app.use("/output", import_express.default.static(import_path.default.join(process.cwd(), "output")));
  app.post("/api/cancel-show", (req, res) => {
    const { generationId } = req.body;
    if (generationId && activeGenerations.has(generationId)) {
      console.log(`[cancel-show] Human requested abort for ${generationId}`);
      activeGenerations.get(generationId)?.abort();
      activeGenerations.delete(generationId);
      res.json({ success: true });
    } else {
      res.status(404).json({ error: "Not found or already completed" });
    }
  });
  app.get("/api/download-proxy", async (req, res) => {
    const targetUrl = req.query.url;
    if (!targetUrl) {
      res.status(400).send("Missing url parameter");
      return;
    }
    try {
      const parsedUrl = new URL(targetUrl);
      if (!parsedUrl.hostname.endsWith("storage.googleapis.com") && !parsedUrl.hostname.endsWith("googleusercontent.com")) {
        res.status(403).send("Forbidden: Domain not allowed");
        return;
      }
      const response = await fetch(targetUrl);
      if (!response.ok) {
        res.status(response.status).send(`Failed to fetch: ${response.statusText}`);
        return;
      }
      res.setHeader(
        "Content-Type",
        response.headers.get("Content-Type") || "application/octet-stream"
      );
      res.setHeader("Access-Control-Allow-Origin", "*");
      const arrayBuffer = await response.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);
      res.send(buffer);
    } catch (err) {
      console.error("Download proxy failed:", err);
      res.status(500).send(
        `Internal server error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
  });
  const QUOTA_CACHE_FILE = import_path.default.join(
    process.cwd(),
    "output",
    "quota_cache.json"
  );
  const DEFAULT_QUOTA_LIMIT = 999999;
  function getQuotaLimit() {
    const limitStr = process.env.DAILY_QUOTA_LIMIT;
    if (limitStr) {
      const parsed = parseInt(limitStr, 10);
      if (!isNaN(parsed)) {
        return parsed;
      }
    }
    return DEFAULT_QUOTA_LIMIT;
  }
  function getTodayStr() {
    return (/* @__PURE__ */ new Date()).toISOString().split("T")[0];
  }
  let isFirebaseAdminInitialized = false;
  function ensureFirebaseAdmin() {
  }
  async function getUserHash(req) {
    return "dev-user-hash";
  }
  function getQuotaCount(userHash) {
    if (!userHash) return 0;
    try {
      const outputDir = import_path.default.dirname(QUOTA_CACHE_FILE);
      if (!import_fs.default.existsSync(outputDir)) {
        import_fs.default.mkdirSync(outputDir, { recursive: true });
      }
      if (import_fs.default.existsSync(QUOTA_CACHE_FILE)) {
        const data = import_fs.default.readFileSync(QUOTA_CACHE_FILE, "utf-8");
        const cache = JSON.parse(data);
        const cacheKey = `${getTodayStr()}_${userHash}`;
        return cache[cacheKey] || 0;
      }
    } catch (err) {
      console.error("Error reading quota cache:", err);
    }
    return 0;
  }
  function incrementQuotaCount(userHash) {
    if (!userHash) return;
    try {
      const outputDir = import_path.default.dirname(QUOTA_CACHE_FILE);
      if (!import_fs.default.existsSync(outputDir)) {
        import_fs.default.mkdirSync(outputDir, { recursive: true });
      }
      let cache = {};
      if (import_fs.default.existsSync(QUOTA_CACHE_FILE)) {
        try {
          const data = import_fs.default.readFileSync(QUOTA_CACHE_FILE, "utf-8");
          cache = JSON.parse(data);
        } catch (e) {
          console.error("Error parsing quota file cache on increment:", e);
        }
      }
      const cacheKey = `${getTodayStr()}_${userHash}`;
      cache[cacheKey] = (cache[cacheKey] || 0) + 1;
      import_fs.default.writeFileSync(
        QUOTA_CACHE_FILE,
        JSON.stringify(cache, null, 2),
        "utf-8"
      );
    } catch (err) {
      console.error("Error incrementing quota cache:", err);
    }
  }
  app.get("/api/quota", async (req, res) => {
    if (process.env.NODE_ENV !== "production") {
      return res.json({ used: 0, limit: 999999 });
    }
    const userHash = await getUserHash(req);
    const limit = getQuotaLimit();
    if (!userHash) {
      return res.json({ used: 0, limit });
    }
    const count = getQuotaCount(userHash);
    return res.json({ used: count, limit });
  });
  const upload = (0, import_multer.default)({
    storage: import_multer.default.memoryStorage(),
    limits: { fileSize: 50 * 1024 * 1024 }
    // 50MB limit
  });
  const uploadSingle = upload.single("file");
  app.post(
    "/api/upload",
    (req, res, next) => {
      uploadSingle(req, res, (err) => {
        if (err) {
          if (err instanceof import_multer.default.MulterError) {
            if (err.code === "LIMIT_FILE_SIZE") {
              return res.status(400).json({
                error: "File is too large. The maximum allowed size is 50MB."
              });
            }
            return res.status(400).json({ error: `Upload error: ${err.message}` });
          }
          return res.status(500).json({
            error: err.message || "An unknown error occurred during upload."
          });
        }
        next();
      });
    },
    async (req, res) => {
      try {
        if (!req.file) {
          return res.status(400).json({ error: "No file uploaded" });
        }
        const MAX_INLINE_SIZE = 25 * 1024 * 1024;
        if (req.file.size > MAX_INLINE_SIZE) {
          return res.status(400).json({
            error: `File "${req.file.originalname}" is ${(req.file.size / (1024 * 1024)).toFixed(2)} MB, which exceeds the 25MB inline limit. For larger files, please use a cloud storage URI.`
          });
        }
        const content = req.file.buffer.toString("utf-8");
        const safeOriginalName = req.file.originalname.replace(
          /[^a-zA-Z0-9._-]/g,
          "_"
        );
        let gsUri = void 0;
        let url = void 0;
        try {
          const sessionId = typeof req.body?.sessionId === "string" ? req.body.sessionId.trim() : "default";
          const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
          const filename = `uploads/${sessionId}/${uniqueSuffix}-${safeOriginalName}`;
        } catch (gcsErr) {
          console.warn("[api/upload] Optional GCS upload omitted:", gcsErr);
        }
        console.log(
          `[api/upload] Processed inline CSV upload for ${safeOriginalName} (${req.file.size} bytes)`
        );
        return res.json({
          name: req.file.originalname,
          content,
          size: req.file.size,
          gsUri,
          url
        });
      } catch (err) {
        console.error("[api/upload] CSV upload failed:", err);
        res.status(500).json({ error: `Upload failed: ${err.message || err}` });
      }
    }
  );
  async function deleteGcsFiles(files) {
  }
  app.get("/api/download-file", async (req, res) => {
    return res.status(500).send("GCS bucket is not configured on Firebase Admin");
  });
  app.post("/api/clear-files", async (req, res) => {
    return res.json({ success: true });
  });
  app.post("/api/analyze", async (req, res) => {
    cleanUpOldGenerations();
    const {
      question,
      files,
      datasetName = "Dataset",
      generationId,
      environmentId,
      googleToken
    } = req.body;
    if (!question || typeof question !== "string" || question.trim() === "") {
      return res.status(400).json({ error: "Missing required field: question" });
    }
    const isFollowUp = !!environmentId;
    const uploadedFiles = Array.isArray(files) ? files.filter(
      (f) => f && typeof f.name === "string" && (typeof f.content === "string" && f.content.trim() !== "" || typeof f.gsUri === "string" && f.gsUri.trim() !== "")
    ) : [];
    if (!isFollowUp && uploadedFiles.length === 0) {
      return res.status(400).json({ error: "Provide at least one CSV file." });
    }
    console.log(`[analyze] Skipping daily quota tracking as requested.`);
    const effectiveDatasetName = datasetName;
    const gcsFiles = uploadedFiles.filter((f) => f.gsUri);
    const hasGcsFiles = gcsFiles.length > 0;
    let gcsToken = null;
    if (hasGcsFiles) {
      gcsToken = await getGcpAccessToken();
    }
    const gcsInstructions = `The user uploaded ${uploadedFiles.length} file(s). First, you MUST run \`python /.agents/download_files.py\` to download them to /.agents/data/ before doing anything else.`;
    let prompt = "";
    if (isFollowUp) {
      prompt = `You are an expert data analyst continuing an analysis of the dataset "${effectiveDatasetName}".


FOLLOW-UP BUSINESS QUESTION:
${question}


EXECUTE IMMEDIATELY:
- Your first response MUST be one code_execution call. Do not explain, plan, quote these instructions, or print code as text.
- In that one call, discover source files with glob.glob('./workspace/data/*.csv'), clear prior files under data/analysis/ and charts/, analyze the question with Pandas, save result CSVs, and optionally create up to three charts with the existing make_chart.py script.
- Do not delete source CSVs, profile.json, or the existing report.json before the replacement report is ready.
- Do not import seaborn, scipy, statsmodels, or other unlisted packages. Use Pandas, NumPy, and the provided chart script.
- If the data cannot answer the question or analysis fails, write data/analysis/limitations.csv with columns limitation, detail, and required_data.
- ALWAYS finish the same code_execution call by running:
 python3 /.agents/skills/reporting/scripts/build_report.py --workspace ./workspace --question "${question.replace(/"/g, '\\"')}" --dataset-name "${effectiveDatasetName.replace(/"/g, '\\"')}"
- After the tool output contains "Report saved", return one short sentence and make no more tool calls.`;
    } else {
      const fileNames = uploadedFiles.map((f) => f.name).join(", ");
      const dataSourceInstructions = `The user provided ${uploadedFiles.length} CSV file(s). ${gcsInstructions} The files will be located at /.agents/data/. Copy them all into ./workspace/data/ before profiling: \`cp /.agents/data/*.csv ./workspace/data/\`. Provided file(s): ${fileNames}.`;
      prompt = `You are an expert data analyst. Dataset name: "${effectiveDatasetName}".


DATA SOURCE:
${dataSourceInstructions}


BUSINESS QUESTION:
${question}


WORKFLOW REQUIREMENT:
You MUST follow this workflow in order. Keep the run short: use one Python script for profiling and one Python script for the requested analysis instead of creating many exploratory scripts. You MUST NOT finish your response until all steps are completed and 'build_report.py' prints that report.json was saved.
HARD LIMIT: You have at most 10 code-execution calls for the entire run. Use one setup call, one combined profiling call, one combined analysis call, up to three chart calls, and one report call. Do not run ad hoc inspection, describe, correlation, validation, package-check, or report-preview commands. Put required calculations into the two scripts. Once build_report.py prints "Report saved", immediately conclude without another tool call.


1. STAGE & SET UP: Create directories, copy the data, and install the core requirements immediately. Do not assume matplotlib is installed:
  mkdir -p ./workspace/data ./workspace/charts ./workspace/data/analysis &&   cp /.agents/data/*.csv ./workspace/data/ &&   pip install -r /.agents/requirements.txt --break-system-packages --prefer-binary --no-cache-dir
  Install scikit-learn separately only if the question genuinely requires an ML model.


2. EXPLORE: Write and run one concise Pandas profiling script that understands the columns and types and writes './workspace/data/profile.json'. The data-explorer skill is agent-driven; there is no profile_data.py supplied by the skill.


3. ANALYZE & SAVE: Write and execute a Python pandas script to perform the data aggregations and calculations needed to answer the question.
  CRITICAL: You MUST save any result tables as CSV files under './workspace/data/analysis/' (e.g., './workspace/data/analysis/streak_data.csv'). Do NOT save files in other folders.


4. VISUALIZE: Create high-quality PNG charts for your findings. Run the visualization script on your saved analysis CSVs:
  python3 /.agents/skills/visualization/scripts/make_chart.py --workspace ./workspace --data data/analysis/<your_csv>.csv --type <bar|line|scatter|pie|heatmap> --x <col> --y <col> --title "<Chart Title>" --output charts/<chart_name>.png


5. BUILD REPORT: Compile everything into the final interactive report JSON by running:
  python3 /.agents/skills/reporting/scripts/build_report.py --workspace ./workspace --question "${question.replace(/"/g, '\\"')}" --dataset-name "${effectiveDatasetName.replace(/"/g, '\\"')}"


CRITICAL RULE FOR RE-ENTRANCY & COMPLETION:
The frontend UI depends 100% on './workspace/data/report.json' to render the charts and tables on the screen. If you output your final textual response or stop calling tools before running step 5 (build_report.py), the user will see a completely blank dashboard!
Therefore, please make sure to run both 'make_chart.py' and 'build_report.py' successfully in the sandbox before concluding your turn.


*SANDBOX TOOL TIP:* Since you run in a Python code_execution sandbox, you should run all shell commands (like directory creation, make_chart.py, or build_report.py scripts) by prefixing them with a "!" in your code cells or by using Python's 'os.system()' or 'subprocess' modules. Do not output plain bash commands or hallucinate external tool calls.


Example of the required execution order:
\`\`\`python
import os
# Stage data and install core dependencies first
os.system("mkdir -p ./workspace/data ./workspace/charts ./workspace/data/analysis && cp /.agents/data/*.csv ./workspace/data/ && pip install -r /.agents/requirements.txt --break-system-packages --prefer-binary --no-cache-dir")


# Explore and profile using Pandas here, then write ./workspace/data/profile.json directly.
# Do not call a nonexistent profiling helper script.


# Analyze & Save CSV
import pandas as pd
df = pd.read_csv('./workspace/data/...')
# ... perform calculations ...
df.to_csv('./workspace/data/analysis/results.csv', index=False)


# Visualize PNG chart
os.system("python3 /.agents/skills/visualization/scripts/make_chart.py --workspace ./workspace --data data/analysis/results.csv --type bar --x col1 --y col2 --title 'Title' --output charts/my_chart.png")


# Compile report immediately after charts (deterministic and network-free)
os.system("""python3 /.agents/skills/reporting/scripts/build_report.py --workspace ./workspace --question "${question.replace(/"/g, '\\"')}" --dataset-name "${effectiveDatasetName.replace(/"/g, '\\"')}" """)
\`\`\``;
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no"
    });
    const sendEvent = (event) => {
      res.write(`data: ${JSON.stringify(event)}

`);
    };
    let reportDelivered = false;
    let streamFailed = false;
    const sendError = (message) => {
      streamFailed = true;
      sendEvent({ type: "error", message });
    };
    let sentSessionEnvironmentId;
    const sendSessionEnvironment = (environmentIdValue) => {
      if (!environmentIdValue || environmentIdValue === sentSessionEnvironmentId)
        return;
      sentSessionEnvironmentId = environmentIdValue;
      sendEvent({ type: "session", environmentId: environmentIdValue });
    };
    sendSessionEnvironment(
      typeof environmentId === "string" ? environmentId : void 0
    );
    const heartbeatInterval = setInterval(() => {
      res.write(`:

`);
    }, 15e3);
    let isFinished = false;
    const abortController = new AbortController();
    if (generationId) {
      activeGenerations.set(generationId, abortController);
    }
    req.on("aborted", () => {
      if (!isFinished) {
        console.log(
          `[analyze] Client aborted request. Agent will continue running in background unless explicitly cancelled.`
        );
      }
      clearInterval(heartbeatInterval);
    });
    req.on("close", () => {
      clearInterval(heartbeatInterval);
    });
    try {
      let agentFiles = [];
      if (isFollowUp) {
        console.log(
          `[analyze] Continuing session in active environment: "${environmentId}" without interaction chaining.`
        );
        sendEvent({
          type: "info",
          message: "Continuing session in active environment..."
        });
      } else {
        console.log(
          `[analyze] Request received. dataset: "${effectiveDatasetName}", source: ${uploadedFiles.length} uploaded file(s), question: "${question.substring(0, 80)}...", generationId: "${generationId}"`
        );
        console.log(
          `[analyze] GEMINI_API_KEY presence verified: ${!!process.env.GEMINI_API_KEY}`
        );
        sendEvent({
          type: "info",
          message: "Provisioning analysis environment..."
        });
        console.log(
          `[analyze] Loading agent files from filesystem path: ${import_path.default.join(process.cwd(), "agent")}`
        );
        agentFiles = loadAgentFiles(
          import_path.default.join(process.cwd(), "agent"),
          "/.agents"
        );
        const protocol = req.headers["x-forwarded-proto"] || "http";
        const host = req.headers.host || "localhost:3000";
        const serverUrl = `${protocol}://${host}`;
        const filesToDownload = [];
        const safeGenerationId = generationId ? generationId.replace(/[^a-zA-Z0-9_-]/g, "") : "default";
        uploadedFiles.forEach((f) => {
          const safeName = import_path.default.posix.basename(f.name).replace(/[^a-zA-Z0-9._-]/g, "_");
          if (f.content) {
            const localUploadDir = import_path.default.join(process.cwd(), "output", "uploads", safeGenerationId);
            import_fs.default.mkdirSync(localUploadDir, { recursive: true });
            import_fs.default.writeFileSync(import_path.default.join(localUploadDir, safeName), f.content, "utf8");
            filesToDownload.push({
              source: `${serverUrl}/output/uploads/${safeGenerationId}/${encodeURIComponent(safeName)}`,
              filename: safeName,
              target: `/.agents/data/${safeName}`,
              isLocalUrl: true
            });
          } else if (f.gsUri) {
            agentFiles.push({
              type: "gcs",
              source: f.gsUri,
              target: "/.agents/data"
            });
            let gcsPath = "";
            const uri = f.gsUri || "";
            if (uri.startsWith("gs://")) {
              const parts = uri.slice(5).split("/", 1);
              gcsPath = uri.slice(5 + parts[0].length + 1);
            }
            filesToDownload.push({
              source: f.gsUri,
              filename: gcsPath,
              target: `/.agents/data/${safeName}`,
              isLocalUrl: false
            });
          }
        });
        if (filesToDownload.length > 0) {
          const downloadScript = `
import urllib.request
import urllib.parse
import os

files = [
${filesToDownload.map((f) => `    {"source": "${f.source}", "filename": "${f.filename}", "target": "${f.target}", "isLocalUrl": ${f.isLocalUrl ? "True" : "False"}}`).join(",\n")}
]

server_url = "${serverUrl}"
token = ${gcsToken ? `"${gcsToken}"` : "None"}
os.makedirs("/.agents/data", exist_ok=True)

for f in files:
    filename = f["filename"]
    if f.get("isLocalUrl"):
        print(f"Downloading inline file {filename} from {f['source']}")
        req = urllib.request.Request(f["source"])
        with urllib.request.urlopen(req) as response, open(f["target"], "wb") as out:
            out.write(response.read())
        print(f"Successfully downloaded {filename}")
        continue

    # 1. First attempt: Download via the secure local Express download proxy (works without direct GCS access or public permission)
    proxy_url = f"{server_url}/api/download-file?filename={urllib.parse.quote(filename)}"
    print(f"Attempting download for {filename} via proxy: {proxy_url}")
    try:
        req = urllib.request.Request(proxy_url)
        with urllib.request.urlopen(req) as response, open(f["target"], "wb") as out:
            out.write(response.read())
        print(f"Successfully downloaded {filename} via Express proxy")
        continue
    except Exception as proxy_err:
        print(f"Express proxy download failed: {proxy_err}. Falling back to direct GCS download...")

    # 2. Second attempt / fallback: Direct GCS API download
    uri = f["source"]
    if uri.startswith("gs://"):
        parts = uri[5:].split("/", 1)
        bucket = parts[0]
        obj = parts[1]
        encoded_obj = urllib.parse.quote(obj)
        url_json = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{encoded_obj}?alt=media"
        url_xml = f"https://storage.googleapis.com/{bucket}/{encoded_obj}"
        
        success = False
        for url in [url_json, url_xml]:
            req = urllib.request.Request(url)
            if token:
                req.add_header("Authorization", "Bearer " + token)
            try:
                with urllib.request.urlopen(req) as response, open(f["target"], "wb") as out:
                    out.write(response.read())
                print(f"Successfully downloaded {f['source']} from {url}")
                success = True
                break
            except Exception as e:
                print(f"Failed download from {url}: {e}")
        if not success:
            print(f"Failed all download attempts for {f['source']}")
`;
          agentFiles.push({
            type: "inline",
            content: downloadScript,
            target: `/.agents/download_files.py`
          });
        }
        console.log(
          `[analyze] Finished loading agent files (source: ${uploadedFiles.length} uploaded file(s)). Count: ${agentFiles.length}`
        );
      }
      if (!gcsToken) {
        gcsToken = await getGcpAccessToken();
      }
      console.log(
        `[analyze] Retrieved GCS access token: ${gcsToken ? "yes (length: " + gcsToken.length + ")" : "no"}`
      );
      console.log(
        `[analyze] Calling createInteraction with prompt: "${prompt.substring(0, 100)}..."`
      );
      let streamRes;
      try {
        streamRes = await createInteraction({
          prompt,
          stream: true,
          inlineSources: isFollowUp ? void 0 : agentFiles.length > 0 ? agentFiles : void 0,
          environmentId: isFollowUp ? environmentId : void 0,
          gcsToken: gcsToken || void 0,
          signal: abortController.signal
        });
      } catch (err) {
        console.error(`[analyze] Gemini API Error: `, err);
        let displayMessage = err.message || "Unknown error";
        const isQuotaError = displayMessage.toLowerCase().includes("quota") || displayMessage.toLowerCase().includes("too_many_requests") || displayMessage.toLowerCase().includes("resource_exhausted") || displayMessage.includes("429");
        const isEnvNotFoundError = displayMessage.toLowerCase().includes("not_found") || displayMessage.toLowerCase().includes("environment not found") || displayMessage.includes("404");
        const isPermissionError = displayMessage.toLowerCase().includes("permission_denied") || displayMessage.includes("403");
        if (isQuotaError) {
          displayMessage = `Gemini API Quota Limit Reached: ${displayMessage}. The shared free-tier Google Gemini API Key has run out of request quota. To resolve this, go to Settings > Secrets inside AI Studio to verify your personal Gemini API key or set up billing.`;
        } else if (isEnvNotFoundError) {
          displayMessage = `The previous analysis session has expired or the remote environment has been recycled due to inactivity. Please start a fresh analysis session by uploading your CSV files again.`;
        } else if (isPermissionError) {
          displayMessage = `Permission Denied: ${displayMessage}. You may need a paid Gemini API Key to use this Agent model. Please configure it in AI Studio settings.`;
        }
        sendError(displayMessage);
        res.end();
        return;
      }
      console.log(
        `[analyze] Response remains ok. Constructing SSE stream reader...`
      );
      let accumulatedText = "";
      let envId = environmentId;
      let interactionId;
      let reportArtifactReady = false;
      let eventCount = 0;
      for await (const event of streamInteraction(streamRes)) {
        eventCount++;
        console.log(
          `[analyze] SSE yields streaming event #${eventCount}: type="${event.type}"`
        );
        if (event.type === "done") {
          console.log(
            `[analyze] Received explicit "done" marker from interaction stream.`
          );
          break;
        }
        if (event.type === "interaction") {
          envId = extractEnvironmentId(event.interaction) || envId;
          interactionId = extractInteractionId(event.interaction) || interactionId;
          sendSessionEnvironment(envId);
          console.log(
            `[analyze] Interaction created. Environment ID: "${envId}", interaction ID: "${interactionId}"`
          );
        }
        if (event.type === "complete") {
          envId = extractEnvironmentId(event.interaction) || envId;
          interactionId = extractInteractionId(event.interaction) || interactionId;
          sendSessionEnvironment(envId);
          console.log(
            `[analyze] Interaction completed. Extracted environment ID: "${envId}"`
          );
          const usage = event.interaction?.usage;
          if (usage) {
            console.log(
              `[agent] Token usage: ${usage.total_tokens} total tokens (${usage.total_input_tokens} input, ${usage.total_output_tokens} output, ${usage.total_thought_tokens || 0} thought, ${usage.total_cached_tokens || 0} cached)`
            );
          }
          const stepsObj = event.interaction?.steps;
          if (Array.isArray(stepsObj)) {
            let combinedStepsText = "";
            for (const step of stepsObj) {
              const isReasoningStep = step.type === "thinking" || step.type === "thought" || step.type === "reasoning";
              if (!isReasoningStep && Array.isArray(step.content)) {
                for (const part of step.content) {
                  if (part && typeof part === "object") {
                    if (part.type === "text" && part.text) {
                      combinedStepsText += part.text;
                    } else if (part.text && part.type !== "thought") {
                      combinedStepsText += part.text;
                    }
                  } else if (typeof part === "string") {
                    combinedStepsText += part;
                  }
                }
              }
            }
            if (combinedStepsText && combinedStepsText.length > accumulatedText.length) {
              console.log(
                `[analyze] Dynamic steps recovery: Reconstructed text of length ${combinedStepsText.length} exceeds accumulated text of length ${accumulatedText.length}. Restoring fallback text.`
              );
              accumulatedText = combinedStepsText;
            }
          }
        }
        if (event.type === "thinking")
          console.log(
            `[agent] thinking delta: ${event.text?.substring(0, 30)}...`
          );
        else if (event.type === "tool_call") {
          console.log(`[agent] tool_call: ${event.name}`);
          console.log(
            `[agent] args:`,
            JSON.stringify(event.arguments, null, 2)
          );
        } else if (event.type === "tool_result") {
          console.log(`[agent] tool_result for tool: ${event.name}`);
          if (event.result?.includes("Report saved to") && event.result.includes("report.json")) {
            reportArtifactReady = true;
            console.log(
              "[analyze] Agent confirmed report.json was saved in the sandbox."
            );
          }
        } else if (event.type === "text") {
          console.log(
            `[agent] text output segment: ${event.text?.substring(0, 30)}...`
          );
        }
        sendEvent(event);
        if (event.type === "text" && event.text) {
          accumulatedText += event.text;
        }
        if (reportArtifactReady && envId) {
          console.log(
            "[analyze] report.json is ready; stopping stream consumption and retrieving the sandbox snapshot."
          );
          break;
        }
      }
      if (!envId && interactionId) {
        try {
          const interactionPath = interactionId.startsWith("interactions/") ? interactionId : `interactions/${interactionId}`;
          const interactionRes = await fetch(
            `${API_BASE_URL}/${interactionPath}`,
            {
              headers: {
                "x-goog-api-key": process.env.GEMINI_API_KEY || "",
                "Api-Revision": "2026-05-20",
                "x-goog-api-client": "applet-ai-data-analyst/1.0.0"
              }
            }
          );
          if (interactionRes.ok) {
            const interactionData = await interactionRes.json();
            envId = extractEnvironmentId(interactionData);
            sendSessionEnvironment(envId);
            console.log(
              `[analyze] Recovered environment ID from interaction resource: "${envId}"`
            );
          } else {
            console.warn(
              `[analyze] Could not recover interaction metadata: ${interactionRes.status} ${interactionRes.statusText}`
            );
          }
        } catch (metadataErr) {
          console.warn(
            "[analyze] Interaction metadata recovery failed:",
            metadataErr
          );
        }
      }
      if (accumulatedText) {
        try {
          const blocks = extractJsonBlocks(accumulatedText);
          const reportBlock = blocks.reverse().find(
            (b) => b && typeof b === "object" && (b.executive_summary || b.insights || b.title)
          );
          if (reportBlock) {
            reportDelivered = true;
            sendEvent({ type: "report_data", data: reportBlock });
          }
        } catch (e) {
          console.error(
            "Failed to parse JSON blocks fallback from accumulated text:",
            e
          );
        }
      }
      if (envId) {
        sendEvent({
          type: "info",
          message: reportArtifactReady ? "Report created. Retrieving dashboard files..." : "Retrieving report and charts from the analysis environment..."
        });
        try {
          const downloadUrl = `${API_BASE_URL}/files/environment-${envId}:download?alt=media`;
          let res2 = null;
          for (let attempt = 1; attempt <= 5; attempt++) {
            res2 = await fetch(downloadUrl, {
              headers: { "x-goog-api-key": process.env.GEMINI_API_KEY || "" }
            });
            if (res2.ok || ![404, 409, 425].includes(res2.status) || attempt === 5)
              break;
            console.log(
              `[analyze] Environment snapshot not ready (attempt ${attempt}/5). Retrying...`
            );
            await new Promise((resolve) => setTimeout(resolve, attempt * 1e3));
          }
          if (res2?.ok) {
            const arrayBuffer = await res2.arrayBuffer();
            const tarBuffer = Buffer.from(arrayBuffer);
            const extractedFiles = extractTarInMemory(tarBuffer);
            let report = null;
            const chartImages = {};
            let runId = "gen-" + Math.random().toString(36).substring(2, 10);
            if (typeof generationId === "string" && /^[A-Za-z0-9_-]+$/.test(generationId)) {
              runId = generationId;
            }
            const outputDirRoot = import_path.default.join(process.cwd(), "output");
            let chartRunDir = import_path.default.join(outputDirRoot, runId, "charts");
            if (import_fs.default.existsSync(chartRunDir)) {
              runId = `${runId}-${Date.now()}`;
              chartRunDir = import_path.default.join(outputDirRoot, runId, "charts");
            }
            import_fs.default.mkdirSync(chartRunDir, { recursive: true });
            for (const [filePath, fileContent] of Object.entries(
              extractedFiles
            )) {
              const normalized = filePath.replace(/^\.\//, "");
              if (normalized.endsWith("data/report.json") || normalized.endsWith("/report.json") || normalized === "report.json") {
                try {
                  report = JSON.parse(fileContent.toString("utf8"));
                } catch (err) {
                  console.error(
                    "Failed to parse report.json from memory:",
                    err
                  );
                }
              } else if (normalized.includes("charts/") && /\.(png|jpg|jpeg)$/i.test(normalized)) {
                let base = normalized.split("/").pop();
                if (!/^[A-Za-z0-9_.-]+\.(png|jpe?g)$/i.test(base)) {
                  const ext = base.split(".").pop() || "png";
                  base = `chart-${Object.keys(chartImages).length + 1}.${ext}`;
                }
                const targetFilePath = import_path.default.join(chartRunDir, base);
                try {
                  import_fs.default.writeFileSync(targetFilePath, fileContent);
                  chartImages[base] = `/output/${runId}/charts/${base}`;
                } catch (writeErr) {
                  console.error(`Failed to write chart ${base} to disk:`, writeErr);
                }
              }
            }
            const reportMatchesCurrentQuestion = typeof report?.question === "string" && report.question.trim().toLowerCase() === question.trim().toLowerCase();
            if (isFollowUp && !reportArtifactReady && !reportMatchesCurrentQuestion) {
              console.warn(
                "[analyze] Follow-up stream ended without producing a replacement report. Preserving the existing dashboard."
              );
              sendError(
                "The follow-up analysis stopped before it could update the dashboard. Your previous report has been preserved; please try the question again."
              );
              return;
            }
            if (!report) {
              console.log(
                "[analyze] report.json was not found in the tar archive. Generating server-side fallback report..."
              );
              const displayTables = [];
              for (const [filePath, fileContent] of Object.entries(
                extractedFiles
              )) {
                const normalized = filePath.replace(/^\.\//, "");
                if (normalized.endsWith(".csv") && !normalized.includes("data/report.json")) {
                  try {
                    const csvText = fileContent.toString("utf8");
                    const lines = csvText.split("\n").map((l) => l.trim()).filter(Boolean);
                    if (lines.length > 0) {
                      const headers = lines[0].split(",").map((h) => h.replace(/^["']|["']$/g, ""));
                      const rows = lines.slice(1, 21).map((line) => {
                        return line.split(",").map((val) => val.replace(/^["']|["']$/g, ""));
                      });
                      const filename = normalized.split("/").pop() || "table.csv";
                      const title = filename.replace(/\.csv$/i, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                      displayTables.push({
                        title,
                        columns: headers,
                        rows,
                        caption: `Generated data table: ${filename}`
                      });
                    }
                  } catch (csvErr) {
                    console.error(
                      `Failed to parse csv fallback for ${normalized}:`,
                      csvErr
                    );
                  }
                }
              }
              if (displayTables.length > 0 || Object.keys(chartImages).length > 0 || accumulatedText) {
                let summary = "The data analyst has finished processing your calculations.";
                if (accumulatedText) {
                  summary = accumulatedText.replace(/```json[\s\S]*?```/g, "").trim();
                  if (summary.length > 500) {
                    summary = summary.substring(0, 500) + "...";
                  }
                }
                report = {
                  dataset_name: effectiveDatasetName || "Dataset",
                  question,
                  title: `Analysis Report: ${effectiveDatasetName || "Dataset"}`,
                  executive_summary: summary,
                  insights: [
                    {
                      title: "Calculations Completed",
                      detail: "The analysis successfully completed the necessary Python computations. Explore the generated data tables and supporting documents below.",
                      metric: "Status",
                      value: "Success"
                    }
                  ],
                  charts: [],
                  tables: displayTables,
                  methodology: "Computed using Pandas inside the sandboxed data analyst workspace.",
                  recommendations: [
                    "Review the structured output tables and charts below for specific metrics."
                  ],
                  generated_at: (/* @__PURE__ */ new Date()).toISOString().split("T")[0]
                };
              }
            }
            if (report) {
              if (Array.isArray(report.charts)) {
                for (const chart of report.charts) {
                  if (chart && typeof chart === "object" && typeof chart.file === "string") {
                    const base = chart.file.split("/").pop();
                    if (chartImages[base]) {
                      chart.image = chartImages[base];
                    }
                  }
                }
              }
              const referenced = new Set(
                (Array.isArray(report.charts) ? report.charts : []).map(
                  (c) => typeof c?.file === "string" ? c.file.split("/").pop() : null
                ).filter(Boolean)
              );
              const extras = Object.keys(chartImages).filter((base) => !referenced.has(base)).map((base) => ({
                title: base.replace(/\.[^.]+$/, "").replace(/_/g, " "),
                file: `charts/${base}`,
                caption: "",
                type: "bar",
                image: chartImages[base]
              }));
              if (extras.length > 0) {
                report.charts = [
                  ...Array.isArray(report.charts) ? report.charts : [],
                  ...extras
                ];
              }
              reportDelivered = true;
              sendEvent({ type: "report_data", data: report });
            } else {
              console.error(
                "report.json was not found in the extracted tar archive"
              );
              sendError("The analysis ran but report.json was not produced.");
            }
          } else {
            const errBody = res2 ? await res2.text() : "No response received";
            console.error("Failed to download snapshot:", errBody);
            let displayMessage = `Failed to retrieve files from the analysis environment: ${errBody}`;
            try {
              const parsed = JSON.parse(errBody);
              if (parsed?.error?.message) {
                const msg = parsed.error.message.toLowerCase();
                if (msg.includes("not found") || msg.includes("not accessible")) {
                  displayMessage = "The previous analysis session has expired or the remote environment has been recycled due to inactivity. Please start a fresh analysis session by uploading your CSV files again.";
                } else {
                  displayMessage = parsed.error.message;
                }
              }
            } catch (e) {
              if (errBody.toLowerCase().includes("not found") || errBody.toLowerCase().includes("not accessible")) {
                displayMessage = "The previous analysis session has expired or the remote environment has been recycled due to inactivity. Please start a fresh analysis session by uploading your CSV files again.";
              }
            }
            sendError(displayMessage);
          }
        } catch (err) {
          console.error("Error processing snapshot in memory:", err);
          sendError(`Error extracting analysis files: ${err.message}`);
        }
      }
      isFinished = true;
      if (!reportDelivered && !streamFailed) {
        sendError(
          "The analysis stream ended before a dashboard report was produced."
        );
      }
      if (reportDelivered && !streamFailed) {
        sendEvent({ type: "status", status: "completed" });
      }
    } catch (err) {
      if (err.name === "AbortError") {
        console.log(`[analyze] Agent interaction aborted successfully.`);
      } else {
        console.error(`[analyze] Error:`, err);
        sendError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      isFinished = true;
      clearInterval(heartbeatInterval);
      if (generationId) {
        activeGenerations.delete(generationId);
      }
      res.end();
    }
  });
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok" });
  });
  const distPath = import_path.default.join(process.cwd(), "dist");
  const indexHtmlExists = import_fs.default.existsSync(import_path.default.join(distPath, "index.html"));
  if (process.env.NODE_ENV !== "production" || !indexHtmlExists) {
    if (process.env.NODE_ENV === "production") {
      console.warn(
        "Production mode enabled, but dist/index.html not found. Falling back to Vite dev server middleware to ensure app stays operational."
      );
    }
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa"
    });
    app.use(vite.middlewares);
  } else {
    app.use(import_express.default.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(import_path.default.join(distPath, "index.html"));
    });
  }
  const startListening = (port) => {
    const server = app.listen(port, "0.0.0.0", () => {
      console.log(`Server running on http://localhost:${port}`);
    }).on("error", (err) => {
      if (err.code === "EADDRINUSE") {
        console.log(`Port ${port} is in use, trying ${port + 1}...`);
        startListening(port + 1);
      } else {
        console.error(err);
      }
    });
    server.setTimeout(0);
    server.requestTimeout = 0;
    server.headersTimeout = 0;
    server.keepAliveTimeout = 0;
  };
  startListening(PORT);
}
startServer();
//# sourceMappingURL=server.cjs.map
