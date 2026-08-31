-- MedHall Connect Database Schema
-- PostgreSQL 12+
-- Run this to initialize the database

CREATE SCHEMA medhall;
SET search_path TO medhall;

-- ============================================================================
-- USER PROFILES TABLE
-- ============================================================================
-- Stores user profile information with internal anonymization

CREATE TABLE user_profiles (

    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    internal_user_id UUID NOT NULL UNIQUE,
    language VARCHAR(2) NOT NULL DEFAULT 'en',
    field VARCHAR(50) NOT NULL,
    academic_level VARCHAR(50) NOT NULL,
    country VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_active TIMESTAMP NOT NULL DEFAULT NOW(),
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    ban_reason TEXT,
    ban_until TIMESTAMP,
    reputation_score INT DEFAULT 100,
    risk_score INT DEFAULT 0,
    -- academic_level_rank gives a real sortable order for matching
    -- (VARCHAR comparisons like 'foundation' >= 'year_1' are lexicographic and WRONG).
    academic_level_rank INT NOT NULL DEFAULT 0
);

-- NOTE: MySQL-style inline `INDEX ...` inside CREATE TABLE is not valid
-- PostgreSQL syntax. All indexes are created explicitly below with
-- CREATE INDEX so this file actually runs on managed Postgres
-- (Railway/Render/Supabase/Neon all reject the old inline form).
CREATE INDEX idx_telegram_id ON user_profiles(telegram_id);
CREATE INDEX idx_internal_user_id ON user_profiles(internal_user_id);
CREATE INDEX idx_field_level_rank ON user_profiles(field, academic_level_rank);

-- ============================================================================
-- MATCH SESSIONS TABLE
-- ============================================================================
-- Records of all matching attempts and active sessions

CREATE TABLE match_sessions (

    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,
    asker_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    answerer_internal_id UUID REFERENCES user_profiles(internal_user_id),
    question TEXT NOT NULL,
    topic VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    matched_at TIMESTAMP,
    ended_at TIMESTAMP,
    is_ai_fallback BOOLEAN DEFAULT FALSE,
    ai_provider VARCHAR(50),
    ai_model VARCHAR(100),
    message_count INT DEFAULT 0
);

-- ============================================================================
-- SESSION MESSAGES TABLE
-- ============================================================================
-- All messages within sessions with moderation flags

CREATE TABLE session_messages (

    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES match_sessions(session_id),
    sender_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    content TEXT NOT NULL,
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reason VARCHAR(255),
    is_redacted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- REPORTS TABLE
-- ============================================================================
-- Abuse reports from users

CREATE TABLE reports (

    id SERIAL PRIMARY KEY,
    report_id UUID NOT NULL UNIQUE,
    session_id UUID NOT NULL REFERENCES match_sessions(session_id),
    reporter_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    reported_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    reason VARCHAR(255) NOT NULL,
    evidence TEXT,
    status VARCHAR(50) DEFAULT 'open',
    moderator_notes TEXT,
    resolution TEXT,
    action_taken VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- ============================================================================
-- BLOCKS TABLE
-- ============================================================================
-- User blocking relationships

CREATE TABLE blocks (

    id SERIAL PRIMARY KEY,
    blocking_user_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    blocked_user_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    reason VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(blocking_user_id, blocked_user_id)
);

-- ============================================================================
-- MODERATION ACTIONS TABLE
-- ============================================================================
-- Log of moderation actions taken against users

CREATE TABLE moderation_actions (

    id SERIAL PRIMARY KEY,
    action_id UUID NOT NULL UNIQUE,
    user_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    action_type VARCHAR(50) NOT NULL,
    reason VARCHAR(255),
    duration_hours INT,
    evidence_report_id UUID REFERENCES reports(report_id),
    enforced_by_admin_id INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expired_at TIMESTAMP
);

-- ============================================================================
-- AI USAGE TRACKING TABLE
-- ============================================================================
-- Track AI API usage for cost control

CREATE TABLE ai_usage (

    id SERIAL PRIMARY KEY,
    user_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    session_id UUID NOT NULL REFERENCES match_sessions(session_id),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    tokens_input INT,
    tokens_output INT,
    cost_usd DECIMAL(10, 4),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- RATE LIMIT TRACKING TABLE
-- ============================================================================
-- Track rate limit violations

CREATE TABLE rate_limit_violations (

    id SERIAL PRIMARY KEY,
    user_internal_id UUID NOT NULL REFERENCES user_profiles(internal_user_id),
    violation_type VARCHAR(50),
    count INT DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    window_expires_at TIMESTAMP
);

-- ============================================================================
-- AUDIT LOG TABLE
-- ============================================================================
-- Log of all administrative access

CREATE TABLE audit_log (

    id SERIAL PRIMARY KEY,
    admin_id INT,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSON,
    ip_address INET,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- SYSTEM CONFIGURATION TABLE
-- ============================================================================
-- Dynamic configuration without code changes

CREATE TABLE system_config (

    id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(50),
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_by_admin_id INT
);

-- ============================================================================
-- INSERT DEFAULT CONFIGURATION
-- ============================================================================

INSERT INTO system_config (config_key, config_value, config_type, description) VALUES
('MATCHING_TIMEOUT', '30', 'integer', 'Seconds to wait for human match before AI fallback'),
('MAX_DAILY_AI_USAGE', '100', 'integer', 'Maximum AI responses per user per day'),
('MESSAGE_RATE_LIMIT', '20', 'integer', 'Maximum messages per minute per user'),
('AI_PROVIDER_PRIORITY', 'anthropic,openai,google', 'string', 'Order of AI providers to try'),
('MODERATION_ENABLED', 'true', 'boolean', 'Enable content moderation'),
('OFFICIAL_CHANNEL_URL', 'https://t.me/medhalll', 'string', 'Official MedHall Telegram channel'),
('MESSAGE_RETENTION_DAYS', '90', 'integer', 'Days to retain messages after session end'),
('REPORT_RETENTION_DAYS', '730', 'integer', 'Days to retain abuse reports');

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active sessions view
CREATE VIEW active_sessions AS
SELECT 
    s.session_id,
    s.asker_internal_id,
    s.answerer_internal_id,
    s.topic,
    s.created_at,
    EXTRACT(EPOCH FROM (NOW() - s.created_at)) as age_seconds,
    s.is_ai_fallback
FROM match_sessions s
WHERE s.status = 'active';

-- User statistics view
CREATE VIEW user_statistics AS
SELECT 
    u.internal_user_id,
    COUNT(DISTINCT s.session_id) as total_sessions,
    SUM(CASE WHEN s.asker_internal_id = u.internal_user_id THEN 1 ELSE 0 END) as questions_asked,
    SUM(CASE WHEN s.answerer_internal_id = u.internal_user_id THEN 1 ELSE 0 END) as questions_answered,
    COUNT(DISTINCT r.report_id) as reports_filed,
    u.reputation_score
FROM user_profiles u
LEFT JOIN match_sessions s ON u.internal_user_id IN (s.asker_internal_id, s.answerer_internal_id)
LEFT JOIN reports r ON r.reporter_internal_id = u.internal_user_id
GROUP BY u.internal_user_id, u.reputation_score;

-- Moderation queue view
CREATE VIEW moderation_queue AS
SELECT 
    r.report_id,
    r.session_id,
    r.reason,
    r.status,
    r.created_at,
    COUNT(ma.id) as previous_actions_on_reported_user
FROM reports r
LEFT JOIN moderation_actions ma ON ma.user_internal_id = r.reported_internal_id
WHERE r.status = 'open' OR r.status = 'under_review'
GROUP BY r.report_id, r.session_id, r.reason, r.status, r.created_at
ORDER BY r.created_at ASC;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX idx_user_profiles_field_level ON user_profiles(field, academic_level);
CREATE INDEX idx_sessions_status_created ON match_sessions(status, created_at DESC);
CREATE INDEX idx_messages_session_created ON session_messages(session_id, created_at);
CREATE INDEX idx_reports_created_status ON reports(created_at DESC, status);

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================
-- Assuming application user is 'medhall_app'

-- Revoke public permissions
REVOKE ALL ON ALL TABLES IN SCHEMA medhall FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA medhall FROM PUBLIC;

-- Grant to application user
GRANT USAGE ON SCHEMA medhall TO medhall_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA medhall TO medhall_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA medhall TO medhall_app;

-- Note: For read-only reporting, create additional user
-- CREATE USER medhall_reporter WITH PASSWORD 'secure_password';
-- GRANT USAGE ON SCHEMA medhall TO medhall_reporter;
-- GRANT SELECT ON ALL TABLES IN SCHEMA medhall TO medhall_reporter;

-- Indexes migrated out of CREATE TABLE (MySQL-style inline INDEX is invalid in Postgres)
CREATE INDEX idx_session_id ON match_sessions(session_id);
CREATE INDEX idx_asker ON match_sessions(asker_internal_id);
CREATE INDEX idx_answerer ON match_sessions(answerer_internal_id);
CREATE INDEX idx_status ON match_sessions(status);
CREATE INDEX idx_created_at ON match_sessions(created_at);
CREATE INDEX idx_session ON session_messages(session_id);
CREATE INDEX idx_sender ON session_messages(sender_internal_id);
CREATE INDEX idx_flagged ON session_messages(is_flagged);
CREATE INDEX idx_report_id ON reports(report_id);
CREATE INDEX idx_reporter ON reports(reporter_internal_id);
CREATE INDEX idx_blocking ON blocks(blocking_user_id);
CREATE INDEX idx_blocked ON blocks(blocked_user_id);
CREATE INDEX idx_user ON moderation_actions(user_internal_id);
CREATE INDEX idx_type ON moderation_actions(action_type);
CREATE INDEX idx_provider ON ai_usage(provider);
CREATE INDEX idx_admin ON audit_log(admin_id);
CREATE INDEX idx_action ON audit_log(action);
CREATE INDEX idx_key ON system_config(config_key);
