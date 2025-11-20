import { openDB, type IDBPDatabase } from 'idb';
import type { AnalysisResponse, CachedAnalysis } from '@/types';

const DB_NAME = 'ruh-cache';
const STORE_NAME = 'analyses';
const DB_VERSION = 1;
const CACHE_TTL = 30 * 24 * 60 * 60 * 1000; // 30 days in milliseconds

class CacheManager {
  private db: IDBPDatabase | null = null;

  async init(): Promise<void> {
    if (this.db) return;

    this.db = await openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'url' });
          store.createIndex('timestamp', 'timestamp');
        }
      }
    });
  }

  async get(url: string): Promise<AnalysisResponse | null> {
    await this.init();
    if (!this.db) return null;

    const cached: CachedAnalysis | undefined = await this.db.get(STORE_NAME, url);

    if (!cached) return null;

    // Check if cache is expired
    const age = Date.now() - cached.timestamp;
    if (age > CACHE_TTL) {
      // Delete expired entry
      await this.delete(url);
      return null;
    }

    return cached.data;
  }

  async set(url: string, data: AnalysisResponse): Promise<void> {
    await this.init();
    if (!this.db) return;

    const cached: CachedAnalysis = {
      url,
      data,
      timestamp: Date.now()
    };

    await this.db.put(STORE_NAME, cached);
  }

  async delete(url: string): Promise<void> {
    await this.init();
    if (!this.db) return;

    await this.db.delete(STORE_NAME, url);
  }

  async clearExpired(): Promise<void> {
    await this.init();
    if (!this.db) return;

    const tx = this.db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const index = store.index('timestamp');

    const cutoff = Date.now() - CACHE_TTL;
    const range = IDBKeyRange.upperBound(cutoff);

    let cursor = await index.openCursor(range);
    while (cursor) {
      await cursor.delete();
      cursor = await cursor.continue();
    }

    await tx.done;
  }

  async clear(): Promise<void> {
    await this.init();
    if (!this.db) return;

    await this.db.clear(STORE_NAME);
  }
}

export const cache = new CacheManager();
