import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

export async function POST(req: Request, context: { params: { id: string } }) {
  const body = await req.json();
  const hasClerk = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY);
  const token = hasClerk
    ? await auth().getToken({ template: process.env.CLERK_JWT_TEMPLATE || undefined })
    : null;
  const devToken = process.env.MCP_DEV_TOKEN;

  const resp = await fetch(`${process.env.MCP_BASE_URL}/api/approvals/${context.params.id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && devToken ? { Authorization: devToken } : {})
    },
    body: JSON.stringify({ status: body.status })
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
