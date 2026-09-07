// 分離ワールド(isolated world)側。injected.jsからのフレームを蓄積し、
// popup.jsからのメッセージに応じて開始/停止/エクスポートを行う。
// 記録は既定でOFFであり、かつ牌譜(リプレイ)URL以外では開始できない(対局中の使用を防ぐ)。
//
// 実際に確認したところ、雀魂は "?paipu=..." のクエリが document_start (ページのJSが
// 動く前)の時点で既に失われていることがある(サーバー側のリダイレクト等が原因と推測される)。
// そのため、単に location.href を見るだけでは検出できない。
// background.js が chrome.webNavigation.onBeforeNavigate で「リダイレクトが起きる前の
// 最初のリクエストURL」を記録しているので、ここではそれを問い合わせて使う。

let bestKnownUrl = location.href;

let recording = false;
let frames = [];

function isReplayUrl() {
  return bestKnownUrl.includes("paipu=");
}

chrome.runtime.sendMessage({ type: "MJSOUL_GET_LAST_PAIPU_URL" }, (response) => {
  if (chrome.runtime.lastError) return; // background未起動などは無視してlocation.hrefのままにする
  if (response && response.url) {
    bestKnownUrl = response.url;
  }
});

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
        url: bestKnownUrl,
      });
      return false;

    case "MJSOUL_CAPTURE_START":
      if (!isReplayUrl() && !message.force) {
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
      sendResponse({ frames, url: bestKnownUrl });
      return false;

    default:
      return false;
  }
});
