
export default function DashboardPage() {

  const stats = [
    { title: '재고 부족', count: 5, color: 'bg-red-100 text-red-600' },
    { title: '판매 급등', count: 2, color: 'bg-blue-100 text-blue-600' },
    { title: '오늘 생성된 보고서', count: 1, color: 'bg-green-100 text-green-600' },
  ];

  return (
      <div>
        <h2 className="text-2xl font-bold mb-6">SCM 재고 관리 현황</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {stats.map((stat) => (
              <div key={stat.title} className={`p-6 rounded-xl shadow-sm border ${stat.color} border-gray-200`}>
                <p className="text-sm font-medium opacity-80">{stat.title}</p>
                <p className="text-3xl font-bold mt-2">{stat.count}건</p>
              </div>
          ))}
        </div>

        <div className="mt-8 p-10 bg-white rounded-xl shadow-sm border border-gray-100">
          <p className="text-gray-400 text-center">분석 데이터 로딩 대기 중...</p>
        </div>
      </div>
  );
}