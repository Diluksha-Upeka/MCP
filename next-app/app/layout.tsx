import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import "./globals.css";
import Providers from "./providers"; // We'll create this to wrap NextAuth SessionProvider

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space" });

export const metadata: Metadata = {
  title: "MCP Ops Console",
  description: "Secure MCP operations console with HITL approvals."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={spaceGrotesk.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
