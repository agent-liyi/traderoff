import Database from 'better-sqlite3';
import path from 'path';

const dbPath = path.join(process.cwd(), 'data', 'podcast.db');

let db: Database.Database;

function getDb(): Database.Database {
  if (!db) {
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    db.exec(`
      CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_number TEXT NOT NULL,
        title TEXT NOT NULL,
        guest TEXT,
        description TEXT,
        transcript TEXT,
        cover_image TEXT,
        duration TEXT,
        publish_date TEXT,
        link_xiaoyuzhou TEXT,
        link_apple_podcasts TEXT,
        audio_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `);
  }
  return db;
}

export default getDb;
