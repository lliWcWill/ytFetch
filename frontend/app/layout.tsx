import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ytFetch - YouTube Transcription Tool",
  description: "Fast, accurate YouTube video transcription powered by Groq's lightning-fast AI models. Convert YouTube videos to text, SRT, VTT, or JSON formats.",
  keywords: ["youtube", "transcription", "ai", "groq", "video", "text", "srt", "vtt"],
  authors: [{ name: "ytFetch Team" }],
  viewport: "width=device-width, initial-scale=1",
  themeColor: "#f97316", // Orange theme color for Groq branding
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased dark min-h-screen bg-background text-foreground`}
      >
        {children}
      </body>
    </html>
  );
}
