-- ==============================================================================
-- LensQR Photo & Video QR Generator
-- Migration: 001_create_media_table.sql
-- Description: Creates persistent media metadata table with indexes and RLS.
-- ==============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create public.media table
CREATE TABLE IF NOT EXISTS public.media (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('photo', 'video')),
    title VARCHAR(255) DEFAULT '',
    description TEXT DEFAULT '',
    original_filename VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    qr_code_path TEXT,
    qr_style VARCHAR(50) DEFAULT 'classic',
    creator_token VARCHAR(128) NOT NULL,
    access VARCHAR(50) DEFAULT 'unlisted',
    views_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comments on table and columns for documentation
COMMENT ON TABLE public.media IS 'Metadata for uploaded photos and videos converted to QR codes';
COMMENT ON COLUMN public.media.id IS 'Unique identifier for media and public QR link resolution';
COMMENT ON COLUMN public.media.media_type IS 'Type of media: photo or video';
COMMENT ON COLUMN public.media.storage_path IS 'Object path inside the private qr-media storage bucket';
COMMENT ON COLUMN public.media.creator_token IS 'Cryptographic token required for media deletion and management';
COMMENT ON COLUMN public.media.is_active IS 'Soft-delete flag; true if media is active, false if deleted';

-- Indexes for optimal lookup performance
CREATE INDEX IF NOT EXISTS idx_media_media_type ON public.media(media_type);
CREATE INDEX IF NOT EXISTS idx_media_creator_token ON public.media(creator_token);
CREATE INDEX IF NOT EXISTS idx_media_is_active ON public.media(is_active);
CREATE INDEX IF NOT EXISTS idx_media_created_at ON public.media(created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.media ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role full access (Flask Backend)
CREATE POLICY "Allow service role full access to media"
    ON public.media
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Allow public read of active unlisted media via public API (if needed)
CREATE POLICY "Allow public read of active media"
    ON public.media
    FOR SELECT
    TO anon
    USING (is_active = true);
