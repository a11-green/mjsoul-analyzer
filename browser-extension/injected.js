// ページ本体(MAIN world)で動作し、WebSocket通信を観測してcontent_script.jsへ中継する。
// クライアントのコード自体は一切変更・パッチせず、WebSocketの送受信を横から記録するのみ。
(() => {
  if (window.__mjsoulCaptureInstalled) return;
  window.__mjsoulCaptureInstalled = true;

  const NativeWebSocket = window.WebSocket;
  if (!NativeWebSocket) return;

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  function encodePayload(data, onReady) {
    if (typeof data === "string") {
      onReady({ encoding: "text", data });
      return;
    }
    if (data instanceof ArrayBuffer) {
      onReady({ encoding: "base64", data: arrayBufferToBase64(data) });
      return;
    }
    if (ArrayBuffer.isView(data)) {
      const buf = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
      onReady({ encoding: "base64", data: arrayBufferToBase64(buf) });
      return;
    }
    if (typeof Blob !== "undefined" && data instanceof Blob) {
      const reader = new FileReader();
      reader.onload = () => onReady({ encoding: "base64", data: arrayBufferToBase64(reader.result) });
      reader.onerror = () => onReady({ encoding: "unknown", data: null });
      reader.readAsArrayBuffer(data);
      return;
    }
    onReady({ encoding: "unknown", data: null });
  }

  function emitFrame(direction, socketUrl, data) {
    encodePayload(data, (payload) => {
      window.postMessage(
        {
          source: "mjsoul-capture",
          frame: {
            direction,
            url: socketUrl,
            at: Date.now(),
            ...payload,
          },
        },
        "*"
      );
    });
  }

  class CapturingWebSocket extends NativeWebSocket {
    constructor(url, protocols) {
      super(url, protocols);
      const socketUrl = String(url);
      this.addEventListener("message", (event) => {
        emitFrame("recv", socketUrl, event.data);
      });
    }

    send(data) {
      emitFrame("send", String(this.url), data);
      return super.send(data);
    }
  }

  window.WebSocket = CapturingWebSocket;
})();
