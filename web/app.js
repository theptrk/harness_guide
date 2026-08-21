const transcript = document.getElementById("transcript");
const composer = document.getElementById("composer");
const prompt = document.getElementById("prompt");
const send = document.getElementById("send");
const title = document.getElementById("chat-title");
const newChat = document.getElementById("new-chat");

let streaming = false;

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

function appendMessage(role, text, iso) {
  appendTime(iso);
  const row = document.createElement("div");
  row.className = `row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  const body = document.createElement("p");
  body.className = "body";
  body.textContent = text;
  bubble.append(body);
  if (role === "assistant") {
    bubble.append(actionRow(body));
  }
  row.append(bubble);
  transcript.append(row);
  scrollToEnd();
  return body;
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
  const share = iconButton(
    "Share",
    '<path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M12 16V4M8 8l4-4 4 4"/>',
  );
  const regenerate = iconButton(
    "Regenerate",
    '<path d="M20 12a8 8 0 1 1-2.2-5.5M20 4v5h-5"/>',
  );
  const more = iconButton("More", '<path d="M6 12h.01M12 12h.01M18 12h.01"/>');
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(body.textContent);
  });
  share.addEventListener("click", async () => {
    const text = body.textContent;
    if (navigator.share) {
      await navigator.share({ text });
      return;
    }
    await navigator.clipboard.writeText(text);
  });
  regenerate.addEventListener("click", () => {
    const rows = [...transcript.querySelectorAll(".row.user .body")];
    const lastUser = rows.at(-1);
    if (lastUser) {
      sendMessage(lastUser.textContent, { regenerate: true });
    }
  });
  actions.append(copy, share, regenerate, more);
  return actions;
}

function setTitle(value) {
  title.textContent = value || "New chat";
  document.title = title.textContent;
}

function showError(message) {
  const error = document.createElement("p");
  error.className = "error";
  error.textContent = message;
  transcript.append(error);
  scrollToEnd();
}

async function loadConversation() {
  const response = await fetch("/api/chat");
  if (!response.ok) {
    showError("Could not load the conversation.");
    return;
  }
  const data = await response.json();
  setTitle(data.title);
  transcript.replaceChildren();
  for (const message of data.messages) {
    appendMessage(message.role, message.text, message.at);
  }
}

async function sendMessage(text, options = {}) {
  const value = text.trim();
  if (!value || streaming) {
    return;
  }

  streaming = true;
  setSendEnabled();
  if (!options.regenerate) {
    appendMessage("user", value, new Date().toISOString());
    prompt.value = "";
    resizePrompt();
  } else {
    const assistantRows = transcript.querySelectorAll(".row.assistant");
    assistantRows[assistantRows.length - 1]?.remove();
  }

  const body = appendMessage("assistant", "", new Date().toISOString());
  body.classList.add("caret");

  let response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: value, regenerate: Boolean(options.regenerate) }),
    });
  } catch (error) {
    body.classList.remove("caret");
    body.textContent = "";
    showError(String(error));
    streaming = false;
    setSendEnabled();
    return;
  }

  if (!response.ok || response.body === null) {
    body.classList.remove("caret");
    const payload = await response.text();
    body.parentElement?.parentElement?.remove();
    showError(payload || `Request failed (${response.status})`);
    streaming = false;
    setSendEnabled();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value: chunk, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(chunk, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.split("\n").find((entry) => entry.startsWith("data: "));
        if (!line) {
          continue;
        }
        const event = JSON.parse(line.slice(6));
        if (event.type === "title") {
          setTitle(event.title);
        } else if (event.type === "delta") {
          body.textContent += event.text;
          scrollToEnd();
        } else if (event.type === "error") {
          showError(event.message);
        }
      }
    }
  } finally {
    body.classList.remove("caret");
    if (body.textContent === "") {
      body.textContent = "No answer.";
    }
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
