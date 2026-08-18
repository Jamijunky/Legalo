import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Legalo — civic rights, then a draft",
  description: "Situation-to-action copilot for RTI, consumer and tenant problems in India. Dated official sources only.",
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap"
          rel="stylesheet"
        />
        <meta name="theme-color" content="#1c2438" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>{children}</body>
    </html>
  );
}
