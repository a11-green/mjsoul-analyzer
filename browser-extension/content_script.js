// 分離ワールド(isolated world)側。injected.jsからのフレームを蓄積し、
// popup.jsからのメッセージに応じて開始/停止/エクスポートを行う。
// 記録は既定でOFFであり、かつ牌譜(リプレイ)URL以外では開始できない(対局中の使用を防ぐ)。

let recording = false;
let frames = [];

function isReplayUrl() {
  return location.href.includes("paipu=");
}

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const msg = event.data;
  if (!msg || msg.source !== "mjsoul-capture") return;
  if (!recording) return;
  frames.push(msg.frame);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message && message.type) {
    case "MJSOUL_CAPTURE_STATUS":
      sendResponse({
        recording,
        frameCount: frames.length,
        isReplayUrl: isReplayUrl(),
        url: location.href,
      });
      return false;

    case "MJSOUL_CAPTURE_START":
      if (!isReplayUrl()) {
        sendResponse({ ok: false, error: "牌譜(paipu=)を含むリプレイ画面でのみ開始できます。" });
        return false;
      }
      recording = true;
      sendResponse({ ok: true });
      return false;

    case "MJSOUL_CAPTURE_STOP":
      recording = false;
      sendResponse({ ok: true });
      return false;

    case "MJSOUL_CAPTURE_CLEAR":
      frames = [];
      sendResponse({ ok: true });
      return false;

    case "MJSOUL_CAPTURE_EXPORT":
      sendResponse({ frames, url: location.href });
      return false;

    default:
      return false;
  }
});
