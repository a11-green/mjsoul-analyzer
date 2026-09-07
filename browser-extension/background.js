// content_script.js は document_start (ページのJSが動く前)で読み込まれるが、
// それでもアドレスバー上の "?paipu=..." が既に消えている場合、雀魂側でサーバーの
// リダイレクト等によりページ本体が読み込まれる前にクエリが失われていると考えられる。
//
// chrome.webNavigation.onBeforeNavigate はブラウザが実際にリクエストしようとしている
// 「最初のURL」(リダイレクトが起きる前)を、ページのどんなスクリプトよりも早く観測できる。
// ここでタブごとに「直近でpaipu=を含んでいたリクエストURL」を記録しておき、
// content_script.js からの問い合わせに答える。

const lastPaipuUrlByTab = new Map();

const WATCHED_URL_FILTERS = {
  url: [{ hostEquals: "game.mahjongsoul.com" }, { hostEquals: "mahjongsoul.yo-star.com" }],
};

chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId !== 0) return; // メインフレームのみ対象
  if (details.url.includes("paipu=")) {
    lastPaipuUrlByTab.set(details.tabId, details.url);
  }
}, WATCHED_URL_FILTERS);

chrome.tabs.onRemoved.addListener((tabId) => {
  lastPaipuUrlByTab.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "MJSOUL_GET_LAST_PAIPU_URL") return false;
  const tabId = sender.tab ? sender.tab.id : null;
  sendResponse({ url: tabId !== null ? lastPaipuUrlByTab.get(tabId) || null : null });
  return false;
});
