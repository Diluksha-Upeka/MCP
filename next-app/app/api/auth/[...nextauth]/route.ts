import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // Persist the Google id_token so we can send it to the backend
      if (account) {
        token.id_token = account.id_token;
      }
      return token;
    },
    async session({ session, token }) {
      // Send the id_token to the client session so we can attach it to headers
      (session as any).id_token = token.id_token;
      return session;
    },
  },
});

export { handler as GET, handler as POST };
