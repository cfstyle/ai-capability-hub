/**
 * Message Mock MCP Server — 模拟内部消息系统
 *
 * 独立 Mock 服务，不引用 Hub Core 内部代码。
 * 提供 message__send_notification 和 message__list_pending 两个 mock tools。
 *
 * 使用 @modelcontextprotocol/sdk Streamable HTTP transport + Express。
 */

import express from "express";
import crypto from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const app = express();
app.use(express.json());

// ---------------------------------------------------------------------------
// Mock 数据
// ---------------------------------------------------------------------------

const MOCK_PENDING_MESSAGES = [
  {
    message_id: "msg-a1b2c3d4",
    from: "risk-control@example.com",
    subject: "【待审批】信用债投资额度申请",
    content: "请审批 2024 年度企业信用债投资额度调整方案，详见附件。",
    priority: "high",
    received_at: "2024-12-20T09:30:00Z",
    status: "PENDING",
  },
  {
    message_id: "msg-e5f6g7h8",
    from: "compliance@example.com",
    subject: "【提醒】季度合规报告截止提醒",
    content: "2024年Q4合规报告提交截止日期为 12 月 31 日，请尽快提交。",
    priority: "normal",
    received_at: "2024-12-19T14:15:00Z",
    status: "PENDING",
  },
  {
    message_id: "msg-i9j0k1l2",
    from: "system@example.com",
    subject: "【通知】系统维护公告",
    content: "TICM 系统将于本周六 22:00-次日 02:00 进行例行维护。",
    priority: "low",
    received_at: "2024-12-18T10:00:00Z",
    status: "PENDING",
  },
];

// ---------------------------------------------------------------------------
// Healthcheck (plain HTTP, not MCP)
// ---------------------------------------------------------------------------

app.get("/healthz", (_req, res) => {
  res.json({ status: "ok" });
});

// ---------------------------------------------------------------------------
// MCP Streamable HTTP endpoint
// ---------------------------------------------------------------------------

// TODO(P0验证点):
// 1. 验证 @modelcontextprotocol/sdk StreamableHTTPServerTransport 与 FastMCP Client 之间的连通性
// 2. 确认 session 模式（此处使用 stateless: sessionIdGenerator: undefined），若下游需 session 则开启 randomUUID
// 3. 如 SDK 在 v2.x 中拆分为 @modelcontextprotocol/server 模块，按实际发布包调整 import 路径
app.post("/mcp", async (req, res) => {
  try {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless
    });

    const server = new McpServer({
      name: "Message MCP Server",
      version: "0.1.0",
    });

    // --- Tool: message__send_notification ---
    server.tool(
      "message__send_notification",
      "发送模拟通知消息",
      {
        recipient: z.string().describe("收件人标识"),
        subject: z.string().describe("消息主题"),
        content: z.string().describe("消息正文"),
        priority: z
          .enum(["low", "normal", "high"])
          .default("normal")
          .describe("优先级 (low/normal/high)"),
      },
      async ({ recipient, subject, content, priority }) => {
        const result = {
          message_id: crypto.randomUUID(),
          recipient,
          subject,
          priority,
          status: "MOCK_SENT",
          sent_at: new Date().toISOString(),
          note: "模拟发送，未向真实人员投递",
        };
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    // --- Tool: message__list_pending ---
    server.tool(
      "message__list_pending",
      "查询待处理消息列表",
      {
        user_id: z.string().describe("用户 ID"),
      },
      async ({ user_id }) => {
        const result = {
          user_id,
          pending_count: MOCK_PENDING_MESSAGES.length,
          messages: MOCK_PENDING_MESSAGES,
          data_status: "MOCK",
          source: "Message Mock Server",
        };
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);

    res.on("close", () => {
      transport.close();
      server.close();
    });
  } catch (error) {
    console.error("Error handling MCP request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null,
      });
    }
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const PORT = process.env.PORT || 8082;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Message MCP Server running on http://0.0.0.0:${PORT}/mcp`);
});
