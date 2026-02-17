-- Migration: Add session_type column to assignments and quizzes tables
-- Run this SQL script to update the database schema

-- Add session_type column to assignments table
ALTER TABLE assignments 
ADD COLUMN session_type VARCHAR(20) NOT NULL DEFAULT 'global';

-- Add session_type column to quizzes table
ALTER TABLE quizzes 
ADD COLUMN session_type VARCHAR(20) NOT NULL DEFAULT 'global';

-- Update existing records to have 'global' session_type (already done by DEFAULT)
-- No additional UPDATE needed as DEFAULT handles it

-- Optional: Add index for better query performance
CREATE INDEX idx_assignments_session_type ON assignments(session_type);
CREATE INDEX idx_quizzes_session_type ON quizzes(session_type);
