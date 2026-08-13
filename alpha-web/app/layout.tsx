import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = (requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000").split(",")[0].trim();
  const protocol = (requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https")).split(",")[0].trim();
  const imageUrl = new URL("/og-product-pivot.png", `${protocol}://${host}`).toString();
  const title = "Market OS — Know When the Evidence Is Ready";
  const description = "A live sports-card capital brief that shows what changed, what can be trusted, and when no action is the right action.";
  return {
    title,
    description,
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: { title, description, type: "website", images: [{ url: imageUrl, width: 1536, height: 1024, alt: "Market OS live sports-card capital brief" }] },
    twitter: { card: "summary_large_image", title, description, images: [imageUrl] },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
