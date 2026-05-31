import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]/route";

export async function POST(req: Request, context: { params: { id: string } }) {
  const body = await req.json();
  const session = await getServerSession(authOptions);
  const token = (session as any)?.id_token || process.env.MCP_DEV_TOKEN || "dev-token-from-nextauth";

  const resp = await fetch(`${process.env.MCP_BASE_URL}/api/approvals/${context.params.id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ status: body.status })
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
