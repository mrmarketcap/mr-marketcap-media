/**
 * Mr. Marketcap — Telegram MCP server for Cloudflare Workers (free plan).
 *
 * A tiny remote MCP server (Streamable HTTP, stateless JSON) that lets Claude
 * post to the Mr. Marketcap Telegram channel through the BotFather bot.
 *
 * Settings (Cloudflare dashboard → your Worker → Settings → Variables and Secrets):
 *   BOT_TOKEN      (Secret)  the token from @BotFather
 *   PATH_SECRET    (Secret)  a long random string; the MCP URL is
 *                            https://<worker>.workers.dev/mcp/<PATH_SECRET>
 *   ALLOWED_CHATS  (Text)    comma-separated chats the bot may act on,
 *                            e.g. "@Mr_marketcap,-1003926910242"
 *
 * Anyone without PATH_SECRET gets a 404, and the bot can only touch the chats
 * listed in ALLOWED_CHATS, so a leaked URL can't be used to post elsewhere.
 */

const SERVER_INFO = { name: "mr-marketcap-telegram", version: "1.1.0" };
const SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"];

const chatId = { type: "string", description: "Channel username (e.g. @Mr_marketcap) or numeric chat id." };
const silent = { type: "boolean", description: "Send without a notification sound for subscribers." };
const parseMode = { type: "string", enum: ["HTML", "MarkdownV2"], description: "Optional text formatting mode. Omit for plain text." };

const TOOLS = [
  {
    name: "send_message",
    description: "Send a text message to the channel. Optionally as a reply to an earlier post, and optionally silent.",
    inputSchema: {
      type: "object",
      required: ["chat_id", "text"],
      properties: {
        chat_id: chatId,
        text: { type: "string", description: "Message text (max 4096 characters)." },
        parse_mode: parseMode,
        reply_to_message_id: { type: "integer", description: "message_id of the post to reply to." },
        disable_notification: silent,
        disable_web_page_preview: { type: "boolean", description: "Hide link previews." },
      },
    },
    method: "sendMessage",
  },
  {
    name: "send_photo",
    description: "Send a photo by public HTTPS URL (or Telegram file_id) with an optional caption (max 1024 characters).",
    inputSchema: {
      type: "object",
      required: ["chat_id", "photo"],
      properties: {
        chat_id: chatId,
        photo: { type: "string", description: "Public HTTPS URL of a JPG/PNG under 5 MB, or a file_id." },
        caption: { type: "string", description: "Caption, max 1024 characters." },
        parse_mode: parseMode,
        reply_to_message_id: { type: "integer", description: "message_id of the post to reply to." },
        disable_notification: silent,
      },
    },
    method: "sendPhoto",
  },
  {
    name: "send_poll",
    description: "Send a poll (regular or quiz) to the channel.",
    inputSchema: {
      type: "object",
      required: ["chat_id", "question", "options"],
      properties: {
        chat_id: chatId,
        question: { type: "string" },
        options: { type: "array", items: { type: "string" }, description: "2 to 10 answer options." },
        is_anonymous: { type: "boolean" },
        type: { type: "string", enum: ["regular", "quiz"] },
        correct_option_id: { type: "integer", description: "Zero-based index of the right answer (quiz only)." },
        disable_notification: silent,
      },
    },
    method: "sendPoll",
    transform: (a) => ({ ...a, options: (a.options || []).map((t) => ({ text: String(t) })) }),
  },
  {
    name: "edit_message_text",
    description: "Edit the text of a text-only post the bot sent earlier.",
    inputSchema: {
      type: "object",
      required: ["chat_id", "message_id", "text"],
      properties: {
        chat_id: chatId,
        message_id: { type: "integer" },
        text: { type: "string" },
        parse_mode: parseMode,
      },
    },
    method: "editMessageText",
  },
  {
    name: "edit_message_caption",
    description: "Edit the caption of a photo post the bot sent earlier (no need to delete and repost).",
    inputSchema: {
      type: "object",
      required: ["chat_id", "message_id", "caption"],
      properties: {
        chat_id: chatId,
        message_id: { type: "integer" },
        caption: { type: "string", description: "New caption, max 1024 characters." },
        parse_mode: parseMode,
      },
    },
    method: "editMessageCaption",
  },
  {
    name: "delete_message",
    description: "Delete a post the bot sent in the channel.",
    inputSchema: {
      type: "object",
      required: ["chat_id", "message_id"],
      properties: { chat_id: chatId, message_id: { type: "integer" } },
    },
    method: "deleteMessage",
  },
  {
    name: "get_chat",
    description: "Read channel info: title, description, pinned post.",
    inputSchema: { type: "object", required: ["chat_id"], properties: { chat_id: chatId } },
    method: "getChat",
    readOnly: true,
  },
  {
    name: "get_me",
    description: "Health check: returns the bot's own username and id.",
    inputSchema: { type: "object", properties: {} },
    method: "getMe",
    readOnly: true,
    noChat: true,
  },
  {
    name: "youtube_latest_videos",
    description:
      "List the newest videos of a YouTube channel from its public feed (about the last 15 uploads), newest first. " +
      "Each item has id, title, url, published (ISO time), description, thumbnail URLs and is_short (true for Shorts).",
    inputSchema: {
      type: "object",
      required: ["channel_id"],
      properties: {
        channel_id: { type: "string", description: "YouTube channel id starting with UC, e.g. UCcHXsOPT4wACJI4hVh-zpTA." },
        limit: { type: "integer", description: "How many of the newest videos to return (1-15, default 5)." },
      },
    },
    readOnly: true,
    noChat: true,
    custom: youtubeLatestVideos,
  },
];

function decodeXml(s) {
  return String(s || "")
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&amp;/g, "&");
}

function tag(xml, name) {
  const m = xml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`));
  return m ? decodeXml(m[1]).trim() : "";
}

async function isShort(videoId) {
  // /shorts/<id> answers 200 for a Short and redirects (3xx) for a normal video.
  try {
    const r = await fetch(`https://www.youtube.com/shorts/${videoId}`, { method: "HEAD", redirect: "manual" });
    return r.status === 200;
  } catch {
    return null;
  }
}

async function youtubeLatestVideos(env, args) {
  const channelId = String(args.channel_id || "").trim();
  if (!/^UC[A-Za-z0-9_-]{22}$/.test(channelId)) {
    return { isError: true, content: [{ type: "text", text: "channel_id must look like UCxxxxxxxxxxxxxxxxxxxxxx" }] };
  }
  const limit = Math.min(15, Math.max(1, Number(args.limit) || 5));
  const res = await fetch(`https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`, {
    headers: { "user-agent": "Mozilla/5.0 (mr-marketcap-telegram)" },
  });
  if (!res.ok) {
    return { isError: true, content: [{ type: "text", text: `YouTube feed returned HTTP ${res.status}` }] };
  }
  const xml = await res.text();
  const entries = xml.split("<entry>").slice(1, 1 + limit).map((e) => e.split("</entry>")[0]);
  const videos = await Promise.all(
    entries.map(async (e) => {
      const id = tag(e, "yt:videoId");
      return {
        id,
        title: tag(e, "title"),
        url: `https://www.youtube.com/watch?v=${id}`,
        published: tag(e, "published"),
        description: tag(e, "media:description"),
        thumbnail_maxres: `https://i.ytimg.com/vi/${id}/maxresdefault.jpg`,
        thumbnail_hq: `https://i.ytimg.com/vi/${id}/hqdefault.jpg`,
        is_short: await isShort(id),
      };
    })
  );
  return { isError: false, content: [{ type: "text", text: JSON.stringify({ channel_id: channelId, videos }) }] };
}

function rpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function rpcError(id, code, message) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message } };
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function allowedChats(env) {
  return String(env.ALLOWED_CHATS || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

async function callTelegram(env, method, params) {
  const res = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
}

async function handleToolCall(env, params) {
  const tool = TOOLS.find((t) => t.name === params?.name);
  if (!tool) {
    return { isError: true, content: [{ type: "text", text: `Unknown tool: ${params?.name}` }] };
  }
  let args = params.arguments || {};

  if (!tool.noChat) {
    const allowed = allowedChats(env);
    const requested = String(args.chat_id || "").trim().toLowerCase();
    if (!requested || !allowed.includes(requested)) {
      return {
        isError: true,
        content: [{ type: "text", text: `chat_id "${args.chat_id}" is not in ALLOWED_CHATS.` }],
      };
    }
  }

  if (tool.custom) {
    try {
      return await tool.custom(env, args);
    } catch (e) {
      return { isError: true, content: [{ type: "text", text: `Error: ${e}` }] };
    }
  }

  if (tool.transform) args = tool.transform(args);

  let data;
  try {
    data = await callTelegram(env, tool.method, args);
  } catch (e) {
    return { isError: true, content: [{ type: "text", text: `Network error calling Telegram: ${e}` }] };
  }
  return {
    isError: !data.ok,
    content: [{ type: "text", text: JSON.stringify(data) }],
  };
}

async function handleRpc(env, msg) {
  const { id, method, params } = msg || {};
  const isNotification = id === undefined || id === null;

  if (method === "initialize") {
    const requested = params?.protocolVersion;
    const protocolVersion = SUPPORTED_PROTOCOLS.includes(requested) ? requested : SUPPORTED_PROTOCOLS[0];
    return rpcResult(id, {
      protocolVersion,
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
      instructions:
        "Posts to the Mr. Marketcap Telegram channel through its bot. Photos must be public HTTPS URLs. " +
        "Use disable_notification for follow-up posts to keep the channel quiet.",
    });
  }
  if (method === "ping") return rpcResult(id, {});
  if (method === "tools/list") {
    return rpcResult(id, {
      tools: TOOLS.map(({ name, description, inputSchema, readOnly }) => ({
        name,
        description,
        inputSchema,
        annotations: { readOnlyHint: !!readOnly, destructiveHint: name === "delete_message" },
      })),
    });
  }
  if (method === "tools/call") return rpcResult(id, await handleToolCall(env, params));
  if (isNotification) return null; // e.g. notifications/initialized
  return rpcError(id, -32601, `Method not found: ${method}`);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!env.PATH_SECRET || !env.BOT_TOKEN) {
      return new Response("Server not configured", { status: 500 });
    }
    if (url.pathname !== `/mcp/${env.PATH_SECRET}`) {
      return new Response("Not found", { status: 404 });
    }
    if (request.method === "GET" || request.method === "DELETE") {
      return new Response("Method not allowed", { status: 405, headers: { allow: "POST" } });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: { allow: "POST" } });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json(rpcError(null, -32700, "Parse error"), 400);
    }

    if (Array.isArray(body)) {
      const out = (await Promise.all(body.map((m) => handleRpc(env, m)))).filter(Boolean);
      return out.length ? json(out) : new Response(null, { status: 202 });
    }
    const out = await handleRpc(env, body);
    return out ? json(out) : new Response(null, { status: 202 });
  },
};
