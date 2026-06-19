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
  metadataBase: new URL('https://fasih-sm-scrapper.vercel.app'),
  title: "Dashboard Monitoring SE2026 - BPS Kabupaten Kepulauan Sangihe",
  description: "Aplikasi monitoring real-time progres pendataan lapangan petugas Sensus Ekonomi 2026 BPS Kabupaten Kepulauan Sangihe.",
  icons: {
    icon: "/icon.png",
    shortcut: "/icon.png",
    apple: "/icon.png",
  },
  openGraph: {
    title: "Dashboard Monitoring SE2026 - BPS Kabupaten Kepulauan Sangihe",
    description: "Aplikasi monitoring real-time progres pendataan lapangan petugas Sensus Ekonomi 2026 BPS Kabupaten Kepulauan Sangihe.",
    images: [
      {
        url: "/icon.png",
        width: 512,
        height: 512,
        alt: "Logo BPS Kabupaten Kepulauan Sangihe",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Dashboard Monitoring SE2026 - BPS Kabupaten Kepulauan Sangihe",
    description: "Aplikasi monitoring real-time progres pendataan lapangan petugas Sensus Ekonomi 2026 BPS Kabupaten Kepulauan Sangihe.",
    images: ["/icon.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="id"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
