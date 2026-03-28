/** 설정에서 저장된 기본 페이지 크기를 반환. 미설정 시 50 */
export const getDefaultPageSize = (): number => {
    if (typeof window === "undefined") return 50;
    return parseInt(localStorage.getItem("scm_default_page_size") || "50", 10);
};
