import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ensonho | Vivendas xaponesas",
  description: "Descubre vivendas xaponesas para comprar ou alugar.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="gl">
      <body>{children}</body>
    </html>
  );
}
