import type { Metadata } from "next";
import { Inter, IBM_Plex_Serif, Plus_Jakarta_Sans, IBM_Plex_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";


const inter=Inter({subsets: ['latin'],variable:'--font-inter'})
const ibmPlexSerif=IBM_Plex_Serif({subsets: ['latin'],weight:['400','700'],variable:'--font-ibm-plex-serif'})
// Refonte frontend (partie 1/4) — titres en Plus Jakarta Sans, montants/chiffres
// en IBM Plex Mono (tabular-nums) : voir tailwind.config.ts (font-heading, font-mono).
const plusJakartaSans=Plus_Jakarta_Sans({subsets: ['latin'],weight:['600','700','800'],variable:'--font-plus-jakarta-sans'})
const ibmPlexMono=IBM_Plex_Mono({subsets: ['latin'],weight:['400','500','600'],variable:'--font-ibm-plex-mono'})



export const metadata: Metadata = {
  title: "Krypt",
  description: "Krypt is a modern banking platform  ",
  icons:{
    icon:'/icons/logo.svg'
  }
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={` ${inter.variable} ${ibmPlexSerif.variable} ${plusJakartaSans.variable} ${ibmPlexMono.variable} font-sans antialiased`}
      >
        <TooltipProvider delayDuration={200}>
          {children}
          <Toaster />
        </TooltipProvider>
      </body>
    </html>
  );
}
