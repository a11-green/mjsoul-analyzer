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
// 【重要】実際の検証で、牌譜画面かどうかの確認(background.jsへの問い合わせ)が
// 返ってくるより前に、ログイン・牌譜データ取得の通信が完了してしまうことが判明した
// (idx=33〜34時点で既にheartbeatしか残っていなかった)。そのため「確認できてから
// 記録開始」ではなく、「ページ読み込みと同時に無条件で暫定記録を開始し、後から
// 牌譜画面でないと判明したら即座に破棄する」方式に変更した。
// これにより対局中ページでも一瞬(background.jsからの応答が返るまでの間、通常は
// 数ミリ秒)だけ暫定的にバッファされる可能性はあるが、
//   - 牌譜画面でないと確認され次第フレームは即座に破棄され、
//   - MJSOUL_CAPTURE_EXPORT は isReplayUrl() が真、またはユーザーが明示的に
//     Start(オーバーライド)を押した場合以外は拒否する
// ため、対局中データが外部に出力されることはない(CLAUDE.mdの「対局中には
// 絶対に発動しない」制約を、確認前バッファ+確認後破棄+エクスポート時ガードの
// 三重の仕組みで担保している)。
let recording = true;
let autoStarted = true; // 「牌譜画面である」と確定するまでの暫定記録中フラグ
let userConfirmed = false; // ユーザーが明示的にStart(手動オーバーライド含む)を押したか

function isReplayUrl() {
  return bestKnownUrl.includes("paipu=");
}

function confirmRecording() {
  autoStarted = false; // 牌譜画面と確定したので暫定状態を解除(以後は破棄対象にしない)
}

function discardRecording() {
  recording = false;
  frames = [];
  autoStarted = false;
}

function startRecording({ auto }) {
  recording = true;
  if (auto) {
    confirmRecording();
  } else {
    userConfirmed = true;
  }
}

// location.href の時点で既に paipu= が見えていれば、その場で確定させる。
if (isReplayUrl()) {
  confirmRecording();
}

// background.js に「リダイレクト前の元URL」を問い合わせ、分かり次第、判定を確定させる。
// この問い合わせが返ってくるまでの間も上記の通り暫定記録は既に始まっている。
chrome.runtime.sendMessage({ type: "MJSOUL_GET_LAST_PAIPU_URL" }, (response) => {
  if (!chrome.runtime.lastError && response && response.url) {
    bestKnownUrl = response.url;
  }
  if (isReplayUrl()) {
    confirmRecording();
  } else if (autoStarted && !userConfirmed) {
    // 暫定記録していたが、実はリプレイ画面ではなかったと判明した場合は即座に破棄する。
    discardRecording();
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
      // 牌譜画面と確定していない(=対局中ページ等の可能性が排除できていない)場合、
      // ユーザーが手動オーバーライドで確認していない限りエクスポートを拒否する。
      if (!isReplayUrl() && !userConfirmed) {
        sendResponse({ ok: false, error: "牌譜(paipu=)を含むリプレイ画面と確認できていないため、エクスポートできません。" });
        return false;
      }
      sendResponse({ frames, url: bestKnownUrl });
      return false;

    default:
      return false;
  }
});
