const transcript = document.getElementById("transcript");
const composer = document.getElementById("composer");
const prompt = document.getElementById("prompt");
const send = document.getElementById("send");
const title = document.getElementById("chat-title");
const workspace = document.getElementById("workspace");
const newChat = document.getElementById("new-chat");

let streaming = false;
let assistantBody = null;

function weekdayStamp(iso) {
  const date = iso ? new Date(iso) : new Date();
  return date.toLocaleString(undefined, {
    weekday: "long",
    hour: "numeric",
    minute: "2-digit",
  });
}

function resizePrompt() {
  prompt.style.height = "auto";
  const next = Math.min(prompt.scrollHeight, 200);
  prompt.style.height = `${next}px`;
  prompt.style.overflowY = prompt.scrollHeight > 200 ? "auto" : "hidden";
}

function setSendEnabled() {
  send.disabled = streaming || prompt.value.trim() === "";
}

function scrollToEnd() {
  transcript.scrollTop = transcript.scrollHeight;
}

function lastTimeLabel() {
  const stamps = transcript.querySelectorAll(".time");
  return stamps.length ? stamps[stamps.length - 1].textContent : "";
}

function appendTime(iso) {
  const label = weekdayStamp(iso);
  if (label === lastTimeLabel()) {
    return;
  }
  const time = document.createElement("div");
  time.className = "time";
  time.textContent = label;
  transcript.append(time);
}

function excludedNote() {
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = "excluded from model input";
  return note;
}

function appendMessage(role, text, iso, excluded = false) {
  appendTime(iso);
  const row = document.createElement("div");
  row.className = excluded ? `row ${role} excluded` : `row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  const body = document.createElement("p");
  body.className = "body";
  body.textContent = text;
  bubble.append(body);
  if (excluded) {
    bubble.append(excludedNote());
  } else if (role === "assistant") {
    bubble.append(actionRow(body));
  }
  row.append(bubble);
  transcript.append(row);
  scrollToEnd();
  return body;
}

function appendCard(kind, text, iso, excluded = false) {
  appendTime(iso);
  const row = document.createElement("div");
  row.className = excluded ? `row ${kind} excluded` : `row ${kind}`;
  const card = document.createElement("pre");
  card.className = kind === "tool" ? "tool-card" : "tool-result-card";
  card.textContent = text;
  row.append(card);
  transcript.append(row);
  scrollToEnd();
  return card;
}

function formatToolResult(output) {
  try {
    return JSON.stringify(JSON.parse(output), null, 2);
  } catch {
    return output;
  }
}

function iconButton(label, paths) {
  const button = document.createElement("button");
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`;
  return button;
}

function actionRow(body) {
  const actions = document.createElement("div");
  actions.className = "actions";
  const copy = iconButton(
    "Copy",
    '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  );
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(body.textContent);
  });
  actions.append(copy);
  return actions;
}

function setTitle(value) {
  title.textContent = value || "New chat";
  document.title = title.textContent;
}

function setWorkspace(value) {
  workspace.textContent = value || "";
}

function showError(message) {
  const error = document.createElement("p");
  error.className = "error";
  error.textContent = message;
  transcript.append(error);
  scrollToEnd();
}

function ensureAssistant(iso) {
  if (assistantBody) {
    return assistantBody;
  }
  assistantBody = appendMessage("assistant", "", iso);
  assistantBody.classList.add("caret");
  return assistantBody;
}

async function readSse(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((entry) => entry.startsWith("data: "));
      if (!line) {
        continue;
      }
      onEvent(JSON.parse(line.slice(6)));
    }
  }
}

function handleEvent(event) {
  if (event.type === "title") {
    setTitle(event.title);
  } else if (event.type === "workspace") {
    setWorkspace(event.workspace);
  } else if (event.type === "delta") {
    const body = ensureAssistant(new Date().toISOString());
    body.textContent += event.text;
    scrollToEnd();
  } else if (event.type === "tool") {
    if (assistantBody) {
      assistantBody.classList.remove("caret");
      assistantBody = null;
    }
    appendCard("tool", `${event.name}(${event.arguments})`);
  } else if (event.type === "tool_result") {
    appendCard("tool-result", formatToolResult(event.output));
  } else if (event.type === "error") {
    showError(event.message);
  }
}

async function loadConversation() {
  const response = await fetch("/api/chat");
  if (!response.ok) {
    showError("Could not load the conversation.");
    return;
  }
  const data = await response.json();
  setTitle(data.title);
  setWorkspace(data.workspace);
  transcript.replaceChildren();
  for (const message of data.messages) {
    const excluded = message.in_model_input === false;
    if (message.kind === "user") {
      appendMessage("user", message.text, message.at, excluded);
    } else if (message.kind === "assistant") {
      appendMessage("assistant", message.text, message.at, excluded);
    } else if (message.kind === "tool") {
      appendCard("tool", `${message.name}(${message.arguments})`, message.at, excluded);
    } else if (message.kind === "tool_result") {
      appendCard("tool-result", formatToolResult(message.output), message.at, excluded);
    } else if (message.kind === "turn_failed") {
      showError(message.message);
    }
  }
}

async function sendMessage(text) {
  const value = text.trim();
  if (!value || streaming) {
    return;
  }

  streaming = true;
  assistantBody = null;
  setSendEnabled();
  appendMessage("user", value, new Date().toISOString());
  prompt.value = "";
  resizePrompt();

  let response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: value }),
    });
  } catch (error) {
    showError(String(error));
    streaming = false;
    setSendEnabled();
    return;
  }

  if (!response.ok || response.body === null) {
    const payload = await response.text();
    showError(payload || `Request failed (${response.status})`);
    streaming = false;
    setSendEnabled();
    return;
  }

  try {
    await readSse(response, handleEvent);
  } finally {
    if (assistantBody) {
      assistantBody.classList.remove("caret");
    }
    assistantBody = null;
    streaming = false;
    setSendEnabled();
    prompt.focus();
  }
}

prompt.addEventListener("input", () => {
  resizePrompt();
  setSendEnabled();
});

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(prompt.value);
});

newChat.addEventListener("click", async () => {
  if (streaming) {
    return;
  }
  await fetch("/api/chat/new", { method: "POST" });
  setTitle("New chat");
  transcript.replaceChildren();
  prompt.focus();
});

resizePrompt();
setSendEnabled();
loadConversation();
prompt.focus();
