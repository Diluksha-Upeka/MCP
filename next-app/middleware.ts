import { NextResponse } from "next/server";
import { clerkMiddleware } from "@clerk/nextjs/server";

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const secretKey = process.env.CLERK_SECRET_KEY;

export default publishableKey && secretKey
  ? clerkMiddleware()
  : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"]
};
