"use strict";

const api = {
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  },
  async get(path) {
    const r = await fetch(path);
    return r.json();
  },
};

// --- DOM refs ---
const promptInput   = document.getElementById("prompt-input");
const generateBtn   = document.getElementById("generate-btn");
const validateBtn   = document.getElementById("validate-btn");
const executeBtn    = document.getElementById("execute-btn");
const stopBtn       = document.getElementById("stop-btn");
const clearStopBtn  = document.getElementById("clear-stop-btn");
const codeOutput    = document.getElementById("code-output");
const validPanel    = document.getElementById("validation-panel");
const execStatusMsg = document.getElementById("exec-status-msg");

// Status bar
const dotConn      = document.getElementById("dot-conn");
const lblConn      = document.getElementById("lbl-conn");
const dotSafety    = document.getElementById("dot-safety");
const lblSafety    = document.getElementById("lbl-safety");
const dotStop      = document.getElementById("dot-stop");
const lblStop      = document.getElementById("lbl-stop");

// Stats
const statRobotMode    = document.getElementById("stat-robot-mode");
const statSafetyMode   = document.getElementById("stat-safety-mode");
const statRuntimeState = document.getElementById("stat-runtime-state");
const statJoints       = document.getElementById("stat-joints");
const statTcp          = document.getElementById("stat-tcp");

// --- State ---
let currentCode = "";
let isValid = false;
let stopRequested = false;

// --- Generate ---
generateBtn.addEventListener("click", async () => {
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  setLoading(generateBtn, true);
  clearValidation();
  codeOutput.textContent = "Generating…";
  try {
    const res = await api.post("/api/generate", { prompt });
    if (res.success) {
      currentCode = res.data.code;
      codeOutput.textContent = currentCode;
      await runValidation(currentCode);
    } else {
      codeOutput.textContent = `Error: ${res.error?.message ?? "Unknown error"}`;
    }
  } catch (e) {
    codeOutput.textContent = `Network error: ${e.message}`;
  } finally {
    setLoading(generateBtn, false);
  }
});

// --- Validate ---
validateBtn.addEventListener("click", async () => {
  const code = codeOutput.textContent.trim();
  if (!code || code === "Generating…") return;
  currentCode = code;
  await runValidation(code);
});

async function runValidation(code) {
  setLoading(validateBtn, true);
  try {
    const res = await api.post("/api/validate", { code });
    if (res.success) {
      renderValidation(res.data);
    }
  } finally {
    setLoading(validateBtn, false);
  }
}

function renderValidation(data) {
  validPanel.innerHTML = "";
  isValid = data.valid;
  executeBtn.disabled = !isValid || stopRequested;

  const badge = document.createElement("div");
  badge.className = `diag ${isValid ? "ok" : "error"}`;
  badge.textContent = isValid ? "✓ Valid URScript" : "✗ Validation failed";
  validPanel.appendChild(badge);

  for (const d of data.errors) {
    addDiag("error", d);
  }
  for (const d of data.warnings) {
    addDiag("warning", d);
  }
}

function addDiag(level, d) {
  const el = document.createElement("div");
  el.className = `diag ${level}`;
  el.textContent = d.line ? `L${d.line}: ${d.message}` : d.message;
  validPanel.appendChild(el);
}

function clearValidation() {
  validPanel.innerHTML = "";
  isValid = false;
  executeBtn.disabled = true;
}

// --- Execute ---
executeBtn.addEventListener("click", async () => {
  if (!currentCode || !isValid) return;
  setLoading(executeBtn, true);
  execStatusMsg.textContent = "Sending to robot…";
  try {
    const res = await api.post("/api/execute", { code: currentCode });
    if (res.success) {
      execStatusMsg.textContent = "Executing…";
      pollExecutionStatus();
    } else {
      execStatusMsg.textContent = `Failed: ${res.error?.message ?? "Unknown"}`;
    }
  } finally {
    setLoading(executeBtn, false);
  }
});

async function pollExecutionStatus() {
  const poll = setInterval(async () => {
    const res = await api.get("/api/execution-status");
    if (res.success && res.data) {
      if (!res.data.running) {
        execStatusMsg.textContent = res.data.message ?? "Done";
        clearInterval(poll);
      }
    }
  }, 500);
}

// --- Stop (always enabled) ---
stopBtn.addEventListener("click", async () => {
  stopBtn.disabled = true;
  execStatusMsg.textContent = "Stop requested…";
  try {
    await api.post("/api/stop", {});
  } finally {
    stopBtn.disabled = false;
  }
});

// Keyboard shortcut: Escape pressed twice within 1s triggers stop
let escCount = 0;
let escTimer = null;
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    escCount++;
    clearTimeout(escTimer);
    if (escCount >= 2) {
      escCount = 0;
      stopBtn.click();
    } else {
      escTimer = setTimeout(() => { escCount = 0; }, 1000);
    }
  }
});

// --- Clear stop ---
clearStopBtn.addEventListener("click", async () => {
  await api.post("/api/clear-stop", {});
  execStatusMsg.textContent = "Safety stop cleared";
});

// --- SSE status stream ---
function connectSSE() {
  const es = new EventSource("/api/status");
  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    updateStatus(d);
  };
  es.onerror = () => {
    dotConn.className = "dot warn";
    lblConn.textContent = "Reconnecting…";
    setTimeout(connectSSE, 3000);
    es.close();
  };
}

const SAFETY_LABELS = {"-1": "Unknown", "1": "Normal", "2": "Reduced", "3": "Protective Stop", "4": "Recovery", "5": "Safeguard Stop", "6": "System Emergency", "7": "Robot Emergency", "8": "Violation", "9": "Fault"};
const RUNTIME_LABELS = {"-1": "Unknown", "0": "Stopped", "1": "Paused", "2": "Playing", "3": "Pausing"};
const ROBOT_MODE_LABELS = {"-1": "Unknown", "0": "Disconnected", "1": "Confirm Safety", "3": "Booting", "4": "Power Off", "5": "Power On", "6": "Idle", "7": "Backdrive", "8": "Running"};

function updateStatus(d) {
  // Connection dot
  dotConn.className = d.connected ? "dot ok" : "dot warn";
  lblConn.textContent = d.connected ? "Connected" : "Disconnected";

  // Safety dot
  const safetyLabel = SAFETY_LABELS[String(d.safety_mode)] ?? d.safety_mode;
  dotSafety.className = d.safety_mode === 1 ? "dot ok" : (d.safety_mode === -1 ? "dot" : "dot danger");
  lblSafety.textContent = safetyLabel;

  // Stop dot
  stopRequested = d.stop_requested;
  dotStop.className = d.stop_requested ? "dot danger" : "dot ok";
  lblStop.textContent = d.stop_requested ? "STOP ACTIVE" : "Clear";

  // Stats
  statRobotMode.textContent    = ROBOT_MODE_LABELS[String(d.robot_mode)] ?? d.robot_mode;
  statSafetyMode.textContent   = safetyLabel;
  statRuntimeState.textContent = RUNTIME_LABELS[String(d.runtime_state)] ?? d.runtime_state;
  statJoints.textContent       = d.joint_positions.map(v => v.toFixed(3)).join(", ");
  statTcp.textContent          = d.tcp_pose.map(v => v.toFixed(4)).join(", ");

  executeBtn.disabled = !isValid || d.stop_requested;
  clearStopBtn.style.display = d.stop_requested ? "block" : "none";
}

function setLoading(btn, loading) {
  const spinner = btn.querySelector(".spinner");
  if (spinner) spinner.style.display = loading ? "block" : "none";
  btn.disabled = loading;
}

connectSSE();
