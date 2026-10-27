// Vite reads VITE_API_URL from the environment when building. On your Mac it isn't set,
// so the local API is used.
export const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export function getJson(path) {
  return fetch(`${API_URL}${path}`).then((response) => {
    if (!response.ok) throw new Error(`server error ${response.status}`);
    return response.json();
  });
}