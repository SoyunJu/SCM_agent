"use client";
import { useState } from 'react';

export default function ChatPage() {
    const [msg, setMsg] = useState("");
    return (
        <div className="flex flex-col h-[calc(100vh-100px)]">
            <h2 className="text-2xl font-bold mb-4 text-slate-800">SCM 챗봇</h2>
            <div className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm p-6 overflow-y-auto mb-4">
                <div className="bg-blue-50 text-blue-700 p-4 rounded-2xl max-w-[80%]">
                    안녕하세요! 어떤 재고 현황을 분석해드릴까요?
                </div>
            </div>
            <div className="flex gap-2 bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
                <input
                    type="text"
                    className="flex-1 outline-none px-2"
                    placeholder="질문을 입력하세요..."
                    value={msg}
                    onChange={(e) => setMsg(e.target.value)}
                />
                <button className="bg-blue-600 text-white px-6 py-2 rounded-xl font-bold">전송</button>
            </div>
        </div>
    );
}