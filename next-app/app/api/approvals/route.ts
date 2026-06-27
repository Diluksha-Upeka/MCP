import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]/options";

export async function GET() {
  const session = await getServerSession(authOptions);
  const token = (session as any)?.id_token || process.env.MCP_DEV_TOKEN || "dev-token-from-nextauth";

  const resp = await fetch(`${process.env.MCP_BASE_URL}/api/approvals`, {
    headers: {
      "Authorization": `Bearer ${token}`
    }
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
