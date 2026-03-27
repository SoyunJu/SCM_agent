"use client";

import { useEffect, useState } from "react";
import {
    getAdminUsers, createAdminUser, updateAdminUser,
    deleteAdminUser, changeMyPassword,
} from "@/lib/api";
import { AdminUser } from "@/lib/types";
import { Loader2, Plus, Pencil, Trash2, KeyRound, X } from "lucide-react";

// login/page.tsx 와 동일한 sha256 해싱 유틸
const hashSHA256 = async (text: string): Promise<string> => {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
};

const ROLE_LABEL: Record<string, string> = {
    superadmin: "슈퍼어드민",
    admin:      "관리자",
    readonly:   "읽기전용",
};
const ROLE_COLOR: Record<string, string> = {
    superadmin: "bg-purple-50 text-purple-700",
    admin:      "bg-blue-50 text-blue-700",
    readonly:   "bg-gray-100 text-gray-600",
};

// ────────────── 모달 공통 래퍼 ──────────────
function Modal({ title, onClose, children }: {
    title: string; onClose: () => void; children: React.ReactNode;
}) {
    return (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
                <div className="flex items-center justify-between mb-5">
                    <h3 className="text-base font-semibold text-gray-800">{title}</h3>
                    <button onClick={onClose}><X size={16} className="text-gray-400" /></button>
                </div>
                {children}
            </div>
        </div>
    );
}

// ────────────── 메인 페이지 ──────────────
export default function AdminUsersPage() {
    const [users, setUsers]       = useState<AdminUser[]>([]);
    const [loading, setLoading]   = useState(true);
    const [error, setError]       = useState("");

    // 모달 상태
    const [showAdd, setShowAdd]           = useState(false);
    const [editTarget, setEditTarget]     = useState<AdminUser | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
    const [showPw, setShowPw]             = useState(false);

    // 추가 폼
    const [addForm, setAddForm] = useState({
        username: "", password: "", role: "admin", slack_user_id: "", email: "",
    });

    // 수정 폼
    const [editForm, setEditForm] = useState({
        role: "admin", slack_user_id: "", email: "", is_active: true,
    });

    // 비밀번호 변경 폼
    const [pwForm, setPwForm] = useState({ current_password: "", new_password: "" });

    const [saving, setSaving] = useState(false);
    const [msg, setMsg]       = useState("");

    const load = () => {
        setLoading(true);
        getAdminUsers()
            .then((res) => setUsers(res.data.items))
            .catch(() => setError("목록을 불러오지 못했습니다."))
            .finally(() => setLoading(false));
    };

    useEffect(() => { load(); }, []);

    const flash = (m: string) => {
        setMsg(m);
        setTimeout(() => setMsg(""), 3000);
    };

    // ── 추가 ──
    const handleAdd = async () => {
        setSaving(true);
        try {
            const hashedPw = await hashSHA256(addForm.password);
            await createAdminUser({
                ...addForm,
                password:      hashedPw,
                slack_user_id: addForm.slack_user_id || undefined,
                email:         addForm.email || undefined,
            });
            setShowAdd(false);
            setAddForm({ username: "", password: "", role: "admin", slack_user_id: "", email: "" });
            load();
            flash("✅ 관리자가 추가되었습니다.");
        } catch (e: any) {
            flash(`❌ ${e.response?.data?.detail ?? "추가 실패"}`);
        } finally {
            setSaving(false);
        }
    };

    // ── 수정 ──
    const openEdit = (u: AdminUser) => {
        setEditTarget(u);
        setEditForm({
            role:          u.role,
            slack_user_id: u.slack_user_id ?? "",
            email:         u.email ?? "",
            is_active:     u.is_active,
        });
    };

    const handleEdit = async () => {
        if (!editTarget) return;
        setSaving(true);
        try {
            await updateAdminUser(editTarget.id, {
                role:          editForm.role,
                slack_user_id: editForm.slack_user_id || undefined,
                email:         editForm.email || undefined,
                is_active:     editForm.is_active,
            });
            setEditTarget(null);
            load();
            flash("✅ 수정되었습니다.");
        } catch (e: any) {
            flash(`❌ ${e.response?.data?.detail ?? "수정 실패"}`);
        } finally {
            setSaving(false);
        }
    };

    // ── 삭제 ──
    const handleDelete = async () => {
        if (!deleteTarget) return;
        setSaving(true);
        try {
            await deleteAdminUser(deleteTarget.id);
            setDeleteTarget(null);
            load();
            flash("✅ 삭제되었습니다.");
        } catch (e: any) {
            flash(`❌ ${e.response?.data?.detail ?? "삭제 실패"}`);
        } finally {
            setSaving(false);
        }
    };

    // ── 비밀번호 변경 ──
    const handlePwChange = async () => {
        setSaving(true);
        try {
            const hashedCurrent = await hashSHA256(pwForm.current_password);
            const hashedNew     = await hashSHA256(pwForm.new_password);
            await changeMyPassword({
                current_password: hashedCurrent,
                new_password:     hashedNew,
            });
            setShowPw(false);
            setPwForm({ current_password: "", new_password: "" });
            flash("✅ 비밀번호가 변경되었습니다.");
        } catch (e: any) {
            flash(`❌ ${e.response?.data?.detail ?? "변경 실패"}`);
        } finally {
            setSaving(false);
        }
    };

    // ────────────── 렌더 ──────────────
    if (loading) return (
        <div className="flex items-center justify-center py-20">
            <Loader2 size={32} className="animate-spin text-blue-500" />
        </div>
    );

    if (error) return (
        <p className="text-red-500 text-sm p-8">{error}</p>
    );

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">관리자 관리</h2>
                    <p className="text-gray-400 text-sm mt-1">계정 추가 · 권한 설정 · Slack 연동</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setShowPw(true)}
                        className="flex items-center gap-2 border border-gray-200 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50 transition"
                    >
                        <KeyRound size={14} /> 비밀번호 변경
                    </button>
                    <button
                        onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                    >
                        <Plus size={14} /> 관리자 추가
                    </button>
                </div>
            </div>

            {msg && (
                <p className="text-sm text-gray-700 bg-gray-100 px-4 py-2 rounded-lg">{msg}</p>
            )}

            {/* 목록 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                    <tr className="bg-gray-50 text-gray-500 text-xs">
                        <th className="px-6 py-3 text-left">사용자명</th>
                        <th className="px-6 py-3 text-left">역할</th>
                        <th className="px-6 py-3 text-left">Slack ID</th>
                        <th className="px-6 py-3 text-left">이메일</th>
                        <th className="px-6 py-3 text-left">상태</th>
                        <th className="px-6 py-3 text-left">마지막 로그인</th>
                        <th className="px-6 py-3 text-left">액션</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                    {users.map((u) => (
                        <tr key={u.id} className="hover:bg-gray-50 transition">
                            <td className="px-6 py-3 font-medium text-gray-800">{u.username}</td>
                            <td className="px-6 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLOR[u.role]}`}>
                                        {ROLE_LABEL[u.role] ?? u.role}
                                    </span>
                            </td>
                            <td className="px-6 py-3 text-gray-500 font-mono text-xs">
                                {u.slack_user_id ?? <span className="text-gray-300">-</span>}
                            </td>
                            <td className="px-6 py-3 text-gray-500">
                                {u.email ?? <span className="text-gray-300">-</span>}
                            </td>
                            <td className="px-6 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                        u.is_active ? "bg-green-50 text-green-700" : "bg-red-50 text-red-500"
                                    }`}>
                                        {u.is_active ? "활성" : "비활성"}
                                    </span>
                            </td>
                            <td className="px-6 py-3 text-gray-400 text-xs">
                                {u.last_login_at ? u.last_login_at.slice(0, 16) : "-"}
                            </td>
                            <td className="px-6 py-3">
                                <div className="flex gap-2">
                                    <button onClick={() => openEdit(u)}
                                            className="p-1.5 rounded hover:bg-gray-100 text-gray-400 transition">
                                        <Pencil size={14} />
                                    </button>
                                    <button onClick={() => setDeleteTarget(u)}
                                            className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition">
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>

            {/* ── 추가 모달 ── */}
            {showAdd && (
                <Modal title="관리자 추가" onClose={() => setShowAdd(false)}>
                    <div className="space-y-4">
                        {[
                            { label: "사용자명 *",   key: "username",       type: "text",     placeholder: "admin2" },
                            { label: "비밀번호 *",   key: "password",       type: "password", placeholder: "••••••••" },
                            { label: "Slack User ID", key: "slack_user_id", type: "text",     placeholder: "U012ABCDE (선택)" },
                            { label: "이메일",        key: "email",          type: "email",    placeholder: "user@example.com (선택)" },
                        ].map(({ label, key, type, placeholder }) => (
                            <div key={key}>
                                <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                                <input
                                    type={type}
                                    value={(addForm as any)[key]}
                                    onChange={(e) => setAddForm((p) => ({ ...p, [key]: e.target.value }))}
                                    placeholder={placeholder}
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                                />
                            </div>
                        ))}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">역할 *</label>
                            <select
                                value={addForm.role}
                                onChange={(e) => setAddForm((p) => ({ ...p, role: e.target.value }))}
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                            >
                                <option value="superadmin">슈퍼어드민</option>
                                <option value="admin">관리자</option>
                                <option value="readonly">읽기전용</option>
                            </select>
                        </div>
                        <p className="text-xs text-gray-400">
                            💡 Slack User ID: Slack 앱 → 프로필 → 더보기 → 멤버 ID 복사
                        </p>
                        <div className="flex justify-end gap-2 pt-2">
                            <button onClick={() => setShowAdd(false)}
                                    className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition">
                                취소
                            </button>
                            <button onClick={handleAdd} disabled={saving}
                                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
                                {saving ? <Loader2 size={14} className="animate-spin" /> : "추가"}
                            </button>
                        </div>
                    </div>
                </Modal>
            )}

            {/* ── 수정 모달 ── */}
            {editTarget && (
                <Modal title={`수정 — ${editTarget.username}`} onClose={() => setEditTarget(null)}>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">역할</label>
                            <select
                                value={editForm.role}
                                onChange={(e) => setEditForm((p) => ({ ...p, role: e.target.value }))}
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                            >
                                <option value="superadmin">슈퍼어드민</option>
                                <option value="admin">관리자</option>
                                <option value="readonly">읽기전용</option>
                            </select>
                        </div>
                        {[
                            { label: "Slack User ID", key: "slack_user_id", type: "text",  placeholder: "U012ABCDE" },
                            { label: "이메일",         key: "email",          type: "email", placeholder: "user@example.com" },
                        ].map(({ label, key, type, placeholder }) => (
                            <div key={key}>
                                <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                                <input
                                    type={type}
                                    value={(editForm as any)[key]}
                                    onChange={(e) => setEditForm((p) => ({ ...p, [key]: e.target.value }))}
                                    placeholder={placeholder}
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                                />
                            </div>
                        ))}
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="is_active"
                                checked={editForm.is_active}
                                onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.checked }))}
                                className="rounded"
                            />
                            <label htmlFor="is_active" className="text-sm text-gray-700">계정 활성화</label>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <button onClick={() => setEditTarget(null)}
                                    className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition">
                                취소
                            </button>
                            <button onClick={handleEdit} disabled={saving}
                                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
                                {saving ? <Loader2 size={14} className="animate-spin" /> : "저장"}
                            </button>
                        </div>
                    </div>
                </Modal>
            )}

            {/* ── 삭제 확인 모달 ── */}
            {deleteTarget && (
                <Modal title="관리자 삭제" onClose={() => setDeleteTarget(null)}>
                    <p className="text-sm text-gray-600 mb-6">
                        <span className="font-semibold text-gray-800">{deleteTarget.username}</span> 계정을 삭제하시겠습니까?
                        이 작업은 되돌릴 수 없습니다.
                    </p>
                    <div className="flex justify-end gap-2">
                        <button onClick={() => setDeleteTarget(null)}
                                className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition">
                            취소
                        </button>
                        <button onClick={handleDelete} disabled={saving}
                                className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition disabled:opacity-50">
                            {saving ? <Loader2 size={14} className="animate-spin" /> : "삭제"}
                        </button>
                    </div>
                </Modal>
            )}

            {/* ── 비밀번호 변경 모달 ── */}
            {showPw && (
                <Modal title="비밀번호 변경" onClose={() => setShowPw(false)}>
                    <div className="space-y-4">
                        {[
                            { label: "현재 비밀번호", key: "current_password" },
                            { label: "새 비밀번호",   key: "new_password"     },
                        ].map(({ label, key }) => (
                            <div key={key}>
                                <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                                <input
                                    type="password"
                                    value={(pwForm as any)[key]}
                                    onChange={(e) => setPwForm((p) => ({ ...p, [key]: e.target.value }))}
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                                />
                            </div>
                        ))}
                        <div className="flex justify-end gap-2 pt-2">
                            <button onClick={() => setShowPw(false)}
                                    className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition">
                                취소
                            </button>
                            <button onClick={handlePwChange} disabled={saving}
                                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
                                {saving ? <Loader2 size={14} className="animate-spin" /> : "변경"}
                            </button>
                        </div>
                    </div>
                </Modal>
            )}
        </div>
    );
}
