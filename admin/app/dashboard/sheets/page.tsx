"use client";

import { useEffect, useState } from "react";
import { getSheetsMaster, getSheetsSales, getSheetsStock } from "@/lib/api";
import { RefreshCw } from "lucide-react";

const TABS = ["상품마스터", "일별판매", "재고현황"] as const;
type Tab = typeof TABS[number];

export default function SheetsPage() {
    const [tab, setTab]       = useState<Tab>("상품마스터");
    const [data, setData]     = useState<any[]>([]);
    const [loading, setLoad]  = useState(false);
    const [days, setDays]     = useState(30);

    const fetchData = async () => {
        setLoad(true);
        try {
            let res;
            if (tab === "상품마스터") res = await getSheetsMaster();
            else if (tab === "일별판매") res = await getSheetsSales(days);
            else res = await getSheetsStock();
            setData(res.data.items ?? []);
        } finally {
            setLoad(false);
        }
    };

    useEffect(() => { fetchData(); }, [tab, days]);

    const columns = data.length > 0 ? Object.keys(data[0]) : [];

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">데이터 조회</h2>
                    <p className="text-gray-400 text-sm mt-1">Google Sheets 원본 데이터</p>
                </div>
                <button
                    onClick={fetchData}
                    className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition"
                >
                    <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {/* 탭 */}
            <div className="flex gap-2">
                {TABS.map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                            tab === t ? "bg-blue-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                        }`}
                    >
                        {t}
                    </button>
                ))}
                {tab === "일별판매" && (
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="ml-2 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                    >
                        <option value={7}>최근 7일</option>
                        <option value={30}>최근 30일</option>
                        <option value={90}>최근 90일</option>
                    </select>
                )}
            </div>

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                <div className="px-5 py-3 border-b border-gray-100 text-xs text-gray-400">
                    총 {data.length}건
                </div>
                {loading ? (
                    <div className="py-12 text-center text-gray-400 text-sm">로딩 중...</div>
                ) : data.length === 0 ? (
                    <div className="py-12 text-center text-gray-400 text-sm">데이터 없음</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                        <tr className="bg-gray-50 text-gray-500 text-xs">
                            {columns.map((col) => (
                                <th key={col} className="px-5 py-3 text-left whitespace-nowrap">{col}</th>
                            ))}
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {data.map((row, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition">
                                {columns.map((col) => (
                                    <td key={col} className="px-5 py-2.5 text-gray-700 whitespace-nowrap">
                                        {String(row[col] ?? "-")}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}