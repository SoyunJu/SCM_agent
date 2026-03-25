import Link from 'next/link';
import { LayoutDashboard, AlertTriangle, FileText, MessageSquare } from 'lucide-react';

export default function Sidebar() {
    const menuItems = [
        { name: '대시보드', href: '/', icon: LayoutDashboard },
        { name: '이상 징후', href: '/inventory', icon: AlertTriangle },
        { name: '보고서 이력', href: '/reports', icon: FileText },
        { name: 'AI 챗봇', href: '/chat', icon: MessageSquare },
    ];

    return (
        <div className="w-64 bg-slate-900 text-white h-screen p-4 fixed">
            <h1 className="text-2xl font-bold mb-8 text-blue-400">SCM Admin</h1>
            <nav className="space-y-2">
                {menuItems.map((item) => (
                    <Link key={item.href} href={item.href} className="flex items-center gap-3 p-3 hover:bg-slate-800 rounded-lg transition-colors">
                        <item.icon size={20} />
                        <span>{item.name}</span>
                    </Link>
                ))}
            </nav>
        </div>
    );
}