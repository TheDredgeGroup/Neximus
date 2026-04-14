-- Grok Agent Database Schema
-- Run this to set up your PostgreSQL database

-- Create the database (run this separately first)
-- CREATE DATABASE grok_agent_db;

-- Connect to the database
-- \c grok_agent_db

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: conversations
-- Stores high-level conversation metadata
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    tags TEXT[],  -- For categorizing conversations
    summary TEXT  -- Optional AI-generated summary
);

-- Table: messages
-- Stores individual messages within conversations
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER,  -- Track token usage
    metadata JSONB  -- Store additional info (model used, temperature, etc.)
);

-- Table: web_content
-- Stores fetched web pages (Phase 3, but creating table now)
CREATE TABLE IF NOT EXISTS web_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT NOT NULL UNIQUE,
    title VARCHAR(1000),
    content_markdown TEXT,
    content_text TEXT,
    metadata JSONB,  -- author, date, tags, etc.
    retrieved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    conversation_id UUID REFERENCES conversations(id)  -- Which conversation triggered this fetch
);

-- Table: system_logs
-- Stores agent activity logs
CREATE TABLE IF NOT EXISTS system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_level VARCHAR(20),
    message TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_content_url ON web_content(url);
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at DESC);

-- Function to update conversation timestamp
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations 
    SET updated_at = CURRENT_TIMESTAMP,
        message_count = message_count + 1
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update conversation on new message
DROP TRIGGER IF EXISTS trigger_update_conversation ON messages;
CREATE TRIGGER trigger_update_conversation
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_timestamp();

-- Create a view for easy conversation retrieval with latest message
CREATE OR REPLACE VIEW conversation_summary AS
SELECT 
    c.id,
    c.title,
    c.created_at,
    c.updated_at,
    c.message_count,
    c.tags,
    (SELECT content FROM messages 
     WHERE conversation_id = c.id 
     ORDER BY created_at DESC 
     LIMIT 1) as last_message
FROM conversations c
ORDER BY c.updated_at DESC;

-- Sample query to verify setup
-- SELECT * FROM conversation_summary LIMIT 10;
