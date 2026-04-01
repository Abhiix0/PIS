-- Migration 002: Add API sync timestamps to students table
-- Run: psql -U pis_user -d pis_db -f sql/migrations/002_add_sync_timestamps.sql
ALTER TABLE students ADD COLUMN IF NOT EXISTS github_last_synced   TIMESTAMPTZ;
ALTER TABLE students ADD COLUMN IF NOT EXISTS leetcode_last_synced TIMESTAMPTZ;
