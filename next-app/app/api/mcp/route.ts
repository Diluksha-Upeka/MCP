import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";

export async function POST(req: Request) {
  const body = await req.json();
  const session = await getServerSession();
  
  // Note: For NextAuth with Google, we often send the email or id_token.
  // In a full prod setup, you pass session.id_token to the python backend.
  // For now we just pass a stringified session or mock token if not using JWTs.
  const token = (session as any)?.id_token || process.env.MCP_DEV_TOKEN || "dev-token-from-nextauth";

  const resp = await fetch(`${process.env.MCP_BASE_URL}/api/tools/hybrid_query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ arguments: { query: body.query, auth: { token: token } } })
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
