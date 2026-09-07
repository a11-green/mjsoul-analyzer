const statusEl = document.getElementById("status");
const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const clearBtn = document.getElementById("clear");
const exportBtn = document.getElementById("export");
const forceOverrideEl = document.getElementById("forceOverride");

function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => resolve(tabs[0]));
  });
}

function sendToContentScript(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        resolve(null);
        return;
      }
      resolve(response);
    });
  });
}

async function refreshStatus() {
  const tab = await getActiveTab();
  if (!tab) return;
  const res = await sendToContentScript(tab.id, { type: "MJSOUL_CAPTURE_STATUS" });
  if (!res) {
    statusEl.textContent = "このページでは利用できません。雀魂の牌譜(リプレイ)画面を開いてください。";
    startBtn.disabled = true;
    stopBtn.disabled = true;
    clearBtn.disabled = true;
    exportBtn.disabled = true;
    return;
  }
  const lines = [
    res.isReplayUrl ? "牌譜(リプレイ)画面: OK" : "牌譜(リプレイ)画面ではありません(paipu=を含むURLが必要)",
    res.recording ? "状態: キャプチャ中" : "状態: 停止中",
    `captured: ${res.frameCount} フレーム`,
    `[debug] 検出URL: ${res.url}`,
  ];
  statusEl.textContent = lines.join("\n");
  const canStart = res.isReplayUrl || forceOverrideEl.checked;
  startBtn.disabled = res.recording || !canStart;
  stopBtn.disabled = !res.recording;
  exportBtn.disabled = res.frameCount === 0;
}

forceOverrideEl.addEventListener("change", refreshStatus);

startBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  const res = await sendToContentScript(tab.id, {
    type: "MJSOUL_CAPTURE_START",
    force: forceOverrideEl.checked,
  });
  if (res && res.ok === false) alert(res.error);
  refreshStatus();
});

stopBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  await sendToContentScript(tab.id, { type: "MJSOUL_CAPTURE_STOP" });
  refreshStatus();
});

clearBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  await sendToContentScript(tab.id, { type: "MJSOUL_CAPTURE_CLEAR" });
  refreshStatus();
});

exportBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  const res = await sendToContentScript(tab.id, { type: "MJSOUL_CAPTURE_EXPORT" });
  if (!res || !res.frames || res.frames.length === 0) {
    alert("キャプチャ済みのフレームがありません。");
    return;
  }
  const payload = {
    captured_at: new Date().toISOString(),
    source_url: res.url,
    frame_count: res.frames.length,
    frames: res.frames,
  };
  const json = JSON.stringify(payload, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download(
    {
      url,
      filename: `mjsoul_capture_${Date.now()}.json`,
      saveAs: true,
    },
    () => URL.revokeObjectURL(url)
  );
});

refreshStatus();
