"use client";

import { useState, useRef, useEffect } from "react";
import { chatQuery } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import { Send, Bot, User } from "lucide-react";

const QUICK_QUERIES = [
    "재고 부족한 상품 알려줘",
    "이번 주 많이 팔린 상품 TOP 5",
    "미해결 이상 징후 목록",
    "지금 보고서 만들어줘",
];

export default function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            role: "assistant",
            content: "안녕하세요! SCM Agent입니다. 재고·판매 데이터에 대해 질문해주세요.",
            timestamp: new Date(),
        },
    ]);
    const [input, setInput]       = useState("");
    const [loading, setLoading]   = useState(false);
    const sessionId               = useRef(`session_${Date.now()}`);
    const bottomRef               = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = async (text: string) => {
        if (!text.trim() || loading) return;

        const userMsg: ChatMessage = { role: "user", content: text, timestamp: new Date() };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const res = await chatQuery(text, sessionId.current);
            const assistantMsg: ChatMessage = {
                role: "assistant",
                content: res.data.reply,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: "오류가 발생했습니다. 다시 시도해주세요.", timestamp: new Date() },
            ]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-800">SCM 챗봇</h2>
                <p className="text-gray-400 text-sm mt-1">재고·판매 데이터 자연어 질의</p>
            </div>

            {/* 빠른 질문 */}
            <div className="flex flex-wrap gap-2 mb-4">
                {QUICK_QUERIES.map((q) => (
                    <button
                        key={q}
                        onClick={() => sendMessage(q)}
                        disabled={loading}
                        className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-full text-xs font-medium hover:bg-blue-100 transition disabled:opacity-50"
                    >
                        {q}
                    </button>
                ))}
            </div>

            {/* 메시지 영역 */}
            <div className="flex-1 bg-white rounded-xl border border-gray-100 shadow-sm overflow-y-auto p-6 space-y-4">
                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                            msg.role === "assistant" ? "bg-blue-100" : "bg-gray-100"
                        }`}>
                            {msg.role === "assistant"
                                ? <Bot size={14} className="text-blue-600" />
                                : <User size={14} className="text-gray-500" />
                            }
                        </div>
                        <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                            msg.role === "assistant"
                                ? "bg-gray-50 text-gray-700"
                                : "bg-blue-600 text-white"
                        }`}>
                            {msg.content}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                            <Bot size={14} className="text-blue-600" />
                        </div>
                        <div className="bg-gray-50 rounded-2xl px-4 py-3 text-sm text-gray-400">
                            분석 중...
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* 입력창 */}
            <div className="mt-4 flex gap-3">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
                    placeholder="재고·판매 데이터에 대해 질문하세요..."
                    className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={loading}
                />
                <button
                    onClick={() => sendMessage(input)}
                    disabled={loading || !input.trim()}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-xl transition disabled:opacity-50"
                >
                    <Send size={16} />
                </button>
            </div>
        </div>
    );
}