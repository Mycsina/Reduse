import "../globals.css";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/toaster";
import Navbar from "@/components/Navbar";
import QueryProvider from "@/providers/query-provider";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import "@ant-design/v5-patch-for-react-19";
const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "Vroom - Used Items Listings",
  description: "Find and list used items with ease",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <AntdRegistry>
            <Navbar />
            <main className="container mx-auto p-4">{children}</main>
            <Toaster />
          </AntdRegistry>
        </QueryProvider>
      </body>
    </html>
  );
}
