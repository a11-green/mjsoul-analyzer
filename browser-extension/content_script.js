// 分離ワールド(isolated world)側。injected.jsからのフレームを蓄積し、
// popup.jsからのメッセージに応じて停止/クリア/エクスポートを行う。
//
// 【重要】記録開始のタイミングについて:
// 雀魂はUnity WebGL製で、アセット読み込みなどの起動処理に数秒〜十数秒かかる。
// 実際に検証したところ、この起動処理の間にログイン・牌譜データ取得等の重要な通信が
// すべて完了してしまい、ユーザーが「キャプチャ開始」ボタンを押した時点では手遅れ
// (数十件のリクエストが既に完了済み)になることが確認された。
// そのため、記録は「このページが牌譜(リプレイ)画面であるとプログラム的に確認できた
// 時点」で自動的に開始する。ただし対局中の使用を防ぐという制約は変えていない:
//   - 自動記録は、background.js が chrome.webNavigation.onBeforeNavigate で観測した
//     「リダイレクトが起きる前の元URL」に paipu= が含まれることを確認できた場合にのみ行う。
//   - 後になって「実はpaipu=を含むページではなかった」と判明した場合、
//     それまでに自動的に蓄積したデータは直ちに破棄し、記録も停止する。
//   - 自動判定に失敗した場合のみ、ユーザーが手動でStart(オーバーライド含む)を押す
//     必要があり、その場合はユーザー確認済みとして自動破棄の対象にしない。

let bestKnownUrl = location.href;
let frames = [];
let recording = false;
let autoStarted = false; // ユーザー操作なしで自動的に記録を開始したか
let userConfirmed = false; // ユーザーが明示的にStart(手動オーバーライド含む)を押したか

function isReplayUrl() {
  return bestKnownUrl.includes("paipu=");
}

function startRecording({ auto }) {
  recording = true;
  if (auto) {
    autoStarted = true;
  } else {
    userConfirmed = true;
  }
}

// location.href の時点で既に paipu= が見えていれば、その場で即座に自動記録を始める。
if (isReplayUrl()) {
  startRecording({ auto: true });
}

// background.js に「リダイレクト前の元URL」を問い合わせ、分かり次第、判定をやり直す。
// Unityの起動(数秒〜十数秒)に比べてこの問い合わせは十分高速なため、実際のWebSocket通信が
// 始まるより前に確定するはずである。
chrome.runtime.sendMessage({ type: "MJSOUL_GET_LAST_PAIPU_URL" }, (response) => {
  if (!chrome.runtime.lastError && response && response.url) {
    bestKnownUrl = response.url;
  }
  if (isReplayUrl()) {
    startRecording({ auto: true });
  } else if (autoStarted && !userConfirmed) {
    // 自動開始していたが、実はリプレイ画面ではなかったと判明した場合は破棄する。
    recording = false;
    frames = [];
    autoStarted = false;
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
      startRecording({ auto: false });
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
