"use client";

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';

interface DashboardStats {
    low_stock: number;
    sales_surge: number;
    reports_today: number;
}

export default function DashboardPage() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // 백엔드 API 호출
        apiClient.get('/dashboard/stats')
            .then(data => {
                setStats(data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    if (loading) return <div className="p-8">데이터를 불러오는 중...</div>;

    const displayStats = [
        { title: '재고 부족', count: stats?.low_stock || 0, color: 'bg-red-50 text-red-600', border: 'border-red-100' },
        { title: '판매 급등', count: stats?.sales_surge || 0, color: 'bg-blue-50 text-blue-600', border: 'border-blue-100' },
        { title: '금일 현황', count: stats?.reports_today || 0, color: 'bg-green-50 text-green-600', border: 'border-green-100' },
    ];

    return (
        <div>
            <h2 className="text-2xl font-bold mb-6 text-slate-800">SCM 실시간 현황</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {displayStats.map((stat) => (
                    <div key={stat.title} className={`p-6 rounded-2xl border ${stat.border} ${stat.color} shadow-sm transition-transform hover:scale-105`}>
                        <p className="text-sm font-semibold opacity-70">{stat.title}</p>
                        <p className="text-4xl font-extrabold mt-2">{stat.count}건</p>
                    </div>
                ))}
            </div>

            <div className="mt-8 grid grid-cols-1 gap-6">
                <div className="p-8 bg-white rounded-2xl shadow-sm border border-gray-100">
                    <h3 className="text-lg font-bold mb-4">최근 이상 징후 알림</h3>
                    <p className="text-gray-400">분석 엔진이 새로운 이슈를 감지하면 여기에 표시됩니다.</p>
                </div>
            </div>
        </div>
    );
}