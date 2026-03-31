-- Migration 001: Add platform usernames to students table
-- Run: psql -U pis_user -d pis_db -f sql/migrations/001_add_usernames.sql
ALTER TABLE students ADD COLUMN IF NOT EXISTS github_username VARCHAR(100);
ALTER TABLE students ADD COLUMN IF NOT EXISTS leetcode_username VARCHAR(100);
