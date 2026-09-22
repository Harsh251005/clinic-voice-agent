// The clinic last opened, so "/" returns there. Only a convenience: storage
// can be blocked or empty, and access is always checked against /api/me.
const KEY = "clinic-console:last-clinic";

export function rememberClinic(id: number) {
  try {
    localStorage.setItem(KEY, String(id));
  } catch {}
}

export function lastClinic(): number | null {
  try {
    const id = Number(localStorage.getItem(KEY));
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}
