// 分離ワールド(isolated world)側。injected.jsからのフレームを蓄積し、
// popup.jsからのメッセージに応じて開始/停止/エクスポートを行う。
// 記録は既定でOFFであり、かつ牌譜(リプレイ)URL以外では開始できない(対局中の使用を防ぐ)。
//
// 雀魂クライアントは起動時に "?paipu=..." を読み取った後、アドレスバーのURLを
// "https://game.mahjongsoul.com/" に書き換えてしまう(履歴書き換え)。
// 本スクリプトは document_start (クライアントのJSが動く前)で読み込まれるため、
// この書き換えが起きる前の「最初のURL」を起動時点で保存しておき、以降はそちらを判定に使う。

const initialUrl = location.href;

let recording = false;
let frames = [];

function isReplayUrl() {
  return initialUrl.includes("paipu=") || location.href.includes("paipu=");
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
        url: initialUrl,
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
      sendResponse({ frames, url: initialUrl });
      return false;

    default:
      return false;
  }
});
