import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]/options";

// Initialize Groq client
import { Groq } from "groq-sdk";

export async function POST(req: Request) {
  const body = await req.json();
  const session = await getServerSession(authOptions);
  
  const token = (session as any)?.id_token || process.env.MCP_DEV_TOKEN || "dev-token-from-nextauth";

  // Connect to the MCP Server programmatically via Groq LLM instead of blindly passing it to hybrid_query
  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
  
  // This is a naive tool proxy for demonstration. 
  // In a real app we'd fetch the tools from the MCP server dynamically.
  // TODO: Fetch tool schemas dynamically from the MCP server at startup
  // instead of hardcoding them here. These mirror the canonical definitions
  // in server.py list_tools().
  const tools = [
    {
      type: "function" as const,
      function: {
        name: "get_user_stats",
        description: "Returns a summary of total, active, and inactive user counts.",
        parameters: { type: "object", properties: {}, required: [] }
      }
    },
    {
      type: "function" as const,
      function: {
        name: "get_active_users",
        description: "Fetches all active users and their roles from the enterprise database.",
        parameters: { type: "object", properties: {}, required: [] }
      }
    },
    {
      type: "function" as const,
      function: {
        name: "add_user",
        description: "Adds a new user to the enterprise database.",
        parameters: {
          type: "object",
          properties: {
            name: { type: "string", description: "The full name of the user." },
            role: { type: "string", enum: ["Employee", "Manager", "Admin", "Engineer", "Intern", "Director"], description: "Job role. Defaults to Employee." }
          },
          required: ["name"]
        }
      }
    },
    {
      type: "function" as const,
      function: {
        name: "review_approval_request",
        description: "Approve or reject a pending approval request.",
        parameters: {
          type: "object",
          properties: {
            request_id: { type: "integer", description: "Approval request ID." },
            status: { type: "string", description: "approved or rejected." }
          },
          required: ["request_id", "status"]
        }
      }
    },
    {
      type: "function" as const,
      function: {
        name: "execute_approved_request",
        description: "Executes a previously approved request.",
        parameters: {
          type: "object",
          properties: {
            request_id: { type: "integer", description: "Approved request ID to execute." }
          },
          required: ["request_id"]
        }
      }
    },
    {
      type: "function" as const,
      function: {
        name: "hybrid_query",
        description: "Routes a query across SOPs, logs, or graph data and returns results.",
        parameters: {
          type: "object",
          properties: {
             query: { type: "string" }
          },
          required: ["query"]
        }
      }
    }
  ];

  try {
    const aiResp = await groq.chat.completions.create({
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: body.query }],
      tools: tools,
      tool_choice: "auto"
    });

    const responseMsg = aiResp.choices[0].message;
    
    // If the AI decides to call a tool:
    if (responseMsg.tool_calls && responseMsg.tool_calls.length > 0) {
      const toolCall = responseMsg.tool_calls[0];
      
      // Parse arguments safely
      let args: any = {};
      if (toolCall.function.arguments && toolCall.function.arguments !== "null") {
        args = JSON.parse(toolCall.function.arguments);
      }
      
      // Pass the token into the arguments
      args.auth = { token: token };
      
      // Execute against your Python MCP Server
      const mcpResp = await fetch(`${process.env.MCP_BASE_URL}/api/tools/${toolCall.function.name}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ arguments: args })
      });
      
      const data = await mcpResp.json();
      return NextResponse.json(data, { status: mcpResp.status });
    }
    
    // Just a normal chat response
    return NextResponse.json({ message: responseMsg.content });
    
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
