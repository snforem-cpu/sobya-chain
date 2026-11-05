function response(message, status = 200) {
  return new Response(message, {
    status,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/bridge") return response("Not found", 404);
    if (request.method !== "GET") return response("GET required", 405);
    if (request.headers.get("Upgrade")?.toLowerCase() !== "websocket") {
      return response("WebSocket upgrade required", 426);
    }

    const expected = env.RELAY_TOKEN;
    const supplied = request.headers.get("Authorization") || "";
    if (!expected || supplied !== `Bearer ${expected}`) {
      return response("Unauthorized", 401);
    }

    const room = url.searchParams.get("room") || "";
    const role = url.searchParams.get("role") || "";
    if (!/^[a-zA-Z0-9_-]{1,48}$/.test(room)) return response("Invalid room", 400);
    if (role !== "a" && role !== "b") return response("Invalid role", 400);

    const id = env.RELAY.idFromName(`sobya-relay:${room}`);
    return env.RELAY.get(id).fetch(request);
  },
};

export class SobyaRelay {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    if (request.headers.get("Upgrade")?.toLowerCase() !== "websocket") {
      return response("WebSocket upgrade required", 426);
    }

    const url = new URL(request.url);
    const role = url.searchParams.get("role");
    if (role !== "a" && role !== "b") return response("Invalid role", 400);

    // This first implementation intentionally supports one TCP stream per side.
    // CometBFT's peer reconnects are handled after the previous WebSocket closes.
    if (this.state.getWebSockets(role).length > 0) {
      return response(`Role ${role} already connected`, 409);
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];

    server.serializeAttachment({ role });
    this.state.acceptWebSocket(server, [role]);

    // Do not let either local TCP proxy forward CometBFT bytes until both
    // validators have established their authenticated WebSocket tunnel.
    const sideA = this.state.getWebSockets("a");
    const sideB = this.state.getWebSockets("b");
    if (sideA.length > 0 && sideB.length > 0) {
      for (const socket of [...sideA, ...sideB]) {
        try {
          socket.send("READY");
        } catch {
          socket.close(1011, "Relay initialization failed");
        }
      }
    }

    return new Response(null, { status: 101, webSocket: client });
  }

  webSocketMessage(socket, message) {
    const attachment = socket.deserializeAttachment() || {};
    const peerRole = attachment.role === "a" ? "b" : "a";
    const peers = this.state.getWebSockets(peerRole);
    if (peers.length !== 1) {
      socket.close(1011, "Counterpart is not connected");
      return;
    }

    try {
      peers[0].send(message);
    } catch {
      socket.close(1011, "Relay forwarding failed");
      peers[0].close(1011, "Relay forwarding failed");
    }
  }

  webSocketClose(socket, code, reason) {
    const attachment = socket.deserializeAttachment() || {};
    const peerRole = attachment.role === "a" ? "b" : "a";
    for (const peer of this.state.getWebSockets(peerRole)) {
      try {
        peer.close(1012, "Counterpart disconnected");
      } catch {
        // The peer may already be closed.
      }
    }
  }

  webSocketError(socket) {
    this.webSocketClose(socket, 1011, "WebSocket error");
  }
}
