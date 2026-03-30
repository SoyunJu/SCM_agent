"use client";

import { useState, useRef, useEffect } from "react";
import { chatQuery, getChatHistory, getAiLimitStatus } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import { Send, Bot, User, Loader2 } from "lucide-react";

const QUICK_QUERIES = [
    "재고 부족한 상품 알려줘",
    "이번 주 많이 팔린 상품 TOP 5",
    "미해결 이상 징후 목록",
    "지금 보고서 만들어줘",
];

const WELCOME_MSG: ChatMessage = {
    role: "ASSISTANT",
    content: "안녕하세요! SCM Agent입니다. 재고·판매 데이터에 대해 질문해주세요.",
    timestamp: new Date(),
};

export default function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MSG]);
    const [input, setInput]       = useState("");
    const [loading, setLoading]   = useState(false);
    const [historyLoading, setHistoryLoading] = useState(true);
    const sessionId               = useRef<string>("");
    const bottomRef               = useRef<HTMLDivElement>(null);
    const [limitStatus, setLimitStatus] = useState<{limit: number; used: number; remaining: number; unlimited: boolean} | null>(null);


    // AI 호툴 limit
    useEffect(() => {
        getAiLimitStatus().then((r) => setLimitStatus(r.data)).catch(() => {});
    }, []);

    // 세션 ID 초기화 및 히스토리 로드
    useEffect(() => {
        const initSession = async () => {
            // localStorage에서 세션 ID 가져오거나 새로 생성
            let id = localStorage.getItem("scm_chat_session_id");
            if (!id) {
                id = `session_${Date.now()}`;
                localStorage.setItem("scm_chat_session_id", id);
            }
            sessionId.current = id;

            // 최근 7일 히스토리 로드
            try {
                const res = await getChatHistory(id, 7);
                const historical: ChatMessage[] = res.data.items.map((item: any) => ({
                    role: item.role as "USER" | "ASSISTANT",
                    content: item.message,
                    timestamp: new Date(item.created_at),
                }));
                if (historical.length > 0) {
                    setMessages(historical);
                }
            } catch {
                // 히스토리 로드 실패 시 기본 환영 메시지 유지
            } finally {
                setHistoryLoading(false);
            }
        };
        initSession();
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = async (text: string) => {
        if (!text.trim() || loading || !sessionId.current) return;

        const userMsg: ChatMessage = { role: "USER", content: text, timestamp: new Date() };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const res = await chatQuery(text, sessionId.current);
            setMessages((prev) => [
                ...prev,
                { role: "ASSISTANT", content: res.data.reply, timestamp: new Date() },
            ]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { role: "ASSISTANT", content: "오류가 발생했습니다. 다시 시도해주세요.", timestamp: new Date() },
            ]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            <div className="mb-4">
                <h2 className="text-2xl font-bold text-gray-800">SCM 챗봇</h2>
                <p className="text-gray-400 text-sm mt-1">재고·판매 데이터 자연어 질의 (최근 7일 대화 기록 유지)</p>
            </div>

            {/* 빠른 질문 */}
            <div className="flex flex-wrap gap-2 mb-4">
                {QUICK_QUERIES.map((q) => (
                    <button
                        key={q}
                        onClick={() => sendMessage(q)}
                        disabled={loading || historyLoading}
                        className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-full text-xs font-medium hover:bg-blue-100 transition disabled:opacity-50"
                    >
                        {q}
                    </button>
                ))}
            </div>

            {/* 메시지 영역 */}
            <div className="flex-1 bg-white rounded-xl border border-gray-100 shadow-sm overflow-y-auto p-6 space-y-4">
                {historyLoading ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="flex flex-col items-center gap-2 text-gray-400">
                            <Loader2 size={24} className="animate-spin" />
                            <p className="text-sm">대화 기록 불러오는 중...</p>
                        </div>
                    </div>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex gap-3 ${msg.role === "USER" ? "flex-row-reverse" : ""}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                                    msg.role === "ASSISTANT" ? "bg-blue-100" : "bg-gray-100"
                                }`}>
                                    {msg.role === "ASSISTANT"
                                        ? <Bot size={14} className="text-blue-600" />
                                        : <User size={14} className="text-gray-500" />
                                    }
                                </div>
                                <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                                    msg.role === "ASSISTANT"
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
                                <div className="bg-gray-50 rounded-2xl px-4 py-3 text-sm text-gray-400 flex items-center gap-2">
                                    <Loader2 size={14} className="animate-spin" /> 분석 중...
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </>
                )}
            </div>

            {/* 입력창 */}
            <div className="mt-4 flex gap-3">
                {limitStatus && !limitStatus.unlimited && (
                    <div className={`px-4 py-1.5 text-xs text-right ${
                        limitStatus.remaining === 0 ? "text-red-500" : "text-gray-400"
                    }`}>
                        오늘 사용: {limitStatus.used} / {limitStatus.limit}회
                        {limitStatus.remaining === 0 && " · 한도 초과"}
                    </div>
                )}
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
                    placeholder="재고·판매 데이터에 대해 질문하세요..."
                    className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={loading || historyLoading}
                />
                <button
                    onClick={() => sendMessage(input)}
                    disabled={loading || !input.trim() || historyLoading}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-xl transition disabled:opacity-50"
                >
                    <Send size={16} />
                </button>
            </div>
        </div>
    );
}
