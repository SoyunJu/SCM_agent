import Sidebar from '@/components/layout/Sidebar';
import './globals.css';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
      <html lang="ko">
      <body>
      <div className="flex">
        <Sidebar />
        <main className="ml-64 p-8 w-full bg-gray-50 min-h-screen">
          {children}
        </main>
      </div>
      </body>
      </html>
  );
}