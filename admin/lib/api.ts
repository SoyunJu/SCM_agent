
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/scm';

export const apiClient = {
    // GET
    get: async (endpoint: string) => {
        const res = await fetch(`${BASE_URL}${endpoint}`, {
            cache: 'no-store', // 실시간 데이터를 위해 캐시 끔
        });
        if (!res.ok) throw new Error('데이터를 불러오는데 실패했습니다.');
        return res.json();
    },

    // POST
    post: async (endpoint: string, data: any) => {
        const res = await fetch(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    }
};