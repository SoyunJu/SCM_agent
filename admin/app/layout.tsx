import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "SCM Admin",
    description: "SCM Admin Dashboard",
};

export default function RootLayout({
                                       children,
                                   }: {
    children: React.ReactNode;
}) {
    return (
        <html lang="ko">
        <body>{children}</body>
        </html>
    );
}