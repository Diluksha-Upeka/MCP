import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

export async function POST(req: Request) {
  const body = await req.json();
  const { getToken } = auth();
  const token = await getToken({ template: process.env.CLERK_JWT_TEMPLATE || undefined });
  const devToken = process.env.MCP_DEV_TOKEN;

  const resp = await fetch(`${process.env.MCP_BASE_URL}/api/tools/hybrid_query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && devToken ? { Authorization: devToken } : {})
    },
    body: JSON.stringify({ arguments: { query: body.query, auth: { token: token || devToken || "" } } })
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
