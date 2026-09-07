import type { Metadata } from "next";
import { Nunito_Sans } from "next/font/google";
import "./globals.css";

/**
 * Nunito Sans is the single typeface of the Stitch design system.
 * `next/font` self-hosts it at build time, so there is no request to Google's
 * CDN at runtime and no flash of fallback text.
 */
const nunito = Nunito_Sans({
  variable: "--font-nunito",
  subsets: ["latin"],
  weight: ["600", "700", "800", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Duolingo Clone",
  description: "A gamified language-learning app built with Next.js and FastAPI.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${nunito.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
