import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/providers/AuthProvider";
import { AuthSuccessHandler } from "@/components/AuthSuccessHandler";
import { SidebarProvider } from "@/contexts/SidebarContext";
import Header from "@/components/Header";
import UserSidebar from "@/components/UserSidebar";
import MainContent from "@/components/MainContent";
import "./globals.css";
import { Suspense } from "react";

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
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f97316", // Orange theme color for Groq branding
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased dark min-h-screen bg-background text-foreground`}
        suppressHydrationWarning
      >
        <AuthProvider>
          <SidebarProvider>
            <Suspense fallback={null}>
              <AuthSuccessHandler />
            </Suspense>
            <div className="flex flex-col min-h-screen">
              <Header />
              <UserSidebar />
              <MainContent>
                {children}
              </MainContent>
            </div>
          </SidebarProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
