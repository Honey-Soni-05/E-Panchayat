/**
 * Local cache helpers.
 *
 * This file used to be the app's data layer: it wrote to localStorage and then
 * attempted a background Supabase upsert that failed on four of five tables,
 * because the column names it generated did not exist. Every failure was
 * swallowed into a console warning, so the app looked like it was saving.
 *
 * The database now lives behind the API (see `api.ts`). What remains here is a
 * plain localStorage cache for the screens that have not been migrated yet.
 * Nothing here talks to a server. When the last component stops importing it,
 * delete the file.
 */

export const getPersistentData = <T>(key: string, defaultData: T): T => {
  if (typeof window === 'undefined') return defaultData;

  try {
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved) as T;
    localStorage.setItem(key, JSON.stringify(defaultData));
  } catch (err) {
    console.warn(`Local cache unavailable for "${key}":`, err);
  }
  return defaultData;
};

export const savePersistentData = (key: string, data: unknown): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (err) {
    console.warn(`Could not cache "${key}" locally:`, err);
  }
};

/** Clears every cached dataset — used on sign-out so one user's cache
 *  cannot be read by the next person to sign in on the same machine. */
export const clearPersistentCache = (): void => {
  if (typeof window === 'undefined') return;
  try {
    Object.keys(localStorage)
      .filter((key) => key.startsWith('panchayat_'))
      .forEach((key) => localStorage.removeItem(key));
  } catch {
    /* nothing to clear */
  }
};
