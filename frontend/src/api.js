export const API_URL = "http://127.0.0.1:8000";

export function getJson(path) {
  return fetch(`${API_URL}${path}`).then((response) => {
    if (!response.ok) throw new Error(`server error ${response.status}`);
    return response.json();
  });
}