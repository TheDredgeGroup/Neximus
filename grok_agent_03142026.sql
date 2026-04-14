--
-- PostgreSQL database dump
--

\restrict 8a7OchcdNVH4Fc2W5JkWOhzm0hPwyScYFemPyQIBtbzXsVqleeGGT8lvg0r65R5

-- Dumped from database version 18.0
-- Dumped by pg_dump version 18.0

-- Started on 2026-04-12 10:34:39

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 2 (class 3079 OID 16389)
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- TOC entry 5161 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- TOC entry 259 (class 1255 OID 16462)
-- Name: update_conversation_timestamp(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_conversation_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE conversations 
    SET updated_at = CURRENT_TIMESTAMP,
        message_count = message_count + 1
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_conversation_timestamp() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 227 (class 1259 OID 16594)
-- Name: chores; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chores (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    plc_id uuid,
    tag_id uuid,
    tag_name character varying(255),
    action character varying(20) NOT NULL,
    action_value text,
    schedule_type character varying(20) NOT NULL,
    schedule_value character varying(100),
    days_of_week character varying(50) DEFAULT 'all'::character varying,
    enabled boolean DEFAULT true,
    last_run timestamp without time zone,
    last_result character varying(20),
    last_error text,
    next_run timestamp without time zone,
    run_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.chores OWNER TO postgres;

--
-- TOC entry 5162 (class 0 OID 0)
-- Dependencies: 227
-- Name: TABLE chores; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.chores IS 'Scheduled tasks for PLC operations';


--
-- TOC entry 225 (class 1259 OID 16550)
-- Name: plc_config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plc_config (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    ip_address character varying(45) NOT NULL,
    slot integer DEFAULT 0,
    plc_type character varying(50) NOT NULL,
    enabled boolean DEFAULT true,
    connection_status character varying(20) DEFAULT 'disconnected'::character varying,
    last_connected timestamp without time zone,
    last_error text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.plc_config OWNER TO postgres;

--
-- TOC entry 5163 (class 0 OID 0)
-- Dependencies: 225
-- Name: TABLE plc_config; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.plc_config IS 'Allen-Bradley PLC connection configurations';


--
-- TOC entry 232 (class 1259 OID 16700)
-- Name: active_chores; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.active_chores AS
 SELECT c.id,
    c.name,
    c.description,
    c.tag_name,
    c.action,
    c.schedule_type,
    c.schedule_value,
    c.days_of_week,
    c.next_run,
    c.last_run,
    c.last_result,
    c.run_count,
    p.name AS plc_name,
    p.ip_address AS plc_ip,
    p.plc_type,
    p.connection_status AS plc_status
   FROM (public.chores c
     LEFT JOIN public.plc_config p ON ((c.plc_id = p.id)))
  WHERE (c.enabled = true)
  ORDER BY c.next_run;


ALTER VIEW public.active_chores OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 16825)
-- Name: agent_pending_suggestions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agent_pending_suggestions (
    pending_id integer NOT NULL,
    title text NOT NULL,
    description text,
    detected_timestamp timestamp without time zone DEFAULT now(),
    confidence_level text,
    expected_savings text,
    related_tags text,
    related_routines text,
    conditions text,
    raw_data text,
    reviewed boolean DEFAULT false,
    imported_as_suggestion_id integer
);


ALTER TABLE public.agent_pending_suggestions OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 16824)
-- Name: agent_pending_suggestions_pending_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.agent_pending_suggestions_pending_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.agent_pending_suggestions_pending_id_seq OWNER TO postgres;

--
-- TOC entry 5164 (class 0 OID 0)
-- Dependencies: 239
-- Name: agent_pending_suggestions_pending_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.agent_pending_suggestions_pending_id_seq OWNED BY public.agent_pending_suggestions.pending_id;


--
-- TOC entry 230 (class 1259 OID 16662)
-- Name: chore_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chore_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    chore_id uuid,
    chore_name character varying(100),
    plc_name character varying(100),
    tag_name character varying(255),
    action character varying(20),
    action_value text,
    result character varying(20) NOT NULL,
    error_message text,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms integer
);


ALTER TABLE public.chore_log OWNER TO postgres;

--
-- TOC entry 5165 (class 0 OID 0)
-- Dependencies: 230
-- Name: TABLE chore_log; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.chore_log IS 'History of chore executions';


--
-- TOC entry 220 (class 1259 OID 16400)
-- Name: conversations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.conversations (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    title character varying(500),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    message_count integer DEFAULT 0,
    tags text[],
    summary text
);


ALTER TABLE public.conversations OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16412)
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    conversation_id uuid,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    token_count integer,
    metadata jsonb
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16464)
-- Name: conversation_summary; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.conversation_summary AS
 SELECT id,
    title,
    created_at,
    updated_at,
    message_count,
    tags,
    ( SELECT messages.content
           FROM public.messages
          WHERE (messages.conversation_id = c.id)
          ORDER BY messages.created_at DESC
         LIMIT 1) AS last_message
   FROM public.conversations c
  ORDER BY updated_at DESC;


ALTER VIEW public.conversation_summary OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 16785)
-- Name: optimization_suggestions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.optimization_suggestions (
    suggestion_id integer NOT NULL,
    title text NOT NULL,
    detailed_description text,
    category text NOT NULL,
    priority text NOT NULL,
    status text NOT NULL,
    related_tags text,
    related_routines text,
    conditions text,
    expected_benefit text,
    estimated_savings_amount numeric,
    estimated_savings_period text,
    implementation_details text,
    created_by text,
    created_timestamp timestamp without time zone DEFAULT now(),
    implemented_date timestamp without time zone,
    implementation_notes text,
    results text,
    agent_can_suggest boolean DEFAULT true,
    requires_approval boolean DEFAULT true,
    plc_id uuid
);


ALTER TABLE public.optimization_suggestions OWNER TO postgres;

--
-- TOC entry 235 (class 1259 OID 16784)
-- Name: optimization_suggestions_suggestion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.optimization_suggestions_suggestion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.optimization_suggestions_suggestion_id_seq OWNER TO postgres;

--
-- TOC entry 5166 (class 0 OID 0)
-- Dependencies: 235
-- Name: optimization_suggestions_suggestion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.optimization_suggestions_suggestion_id_seq OWNED BY public.optimization_suggestions.suggestion_id;


--
-- TOC entry 228 (class 1259 OID 16625)
-- Name: reminders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reminders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message text NOT NULL,
    trigger_time timestamp without time zone NOT NULL,
    notify_voice boolean DEFAULT true,
    notify_email boolean DEFAULT false,
    notify_sms boolean DEFAULT false,
    repeat_type character varying(20) DEFAULT 'once'::character varying,
    repeat_interval integer,
    repeat_until timestamp without time zone,
    repeat_days character varying(50),
    status character varying(20) DEFAULT 'pending'::character varying,
    sent_at timestamp without time zone,
    snooze_until timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.reminders OWNER TO postgres;

--
-- TOC entry 5167 (class 0 OID 0)
-- Dependencies: 228
-- Name: TABLE reminders; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.reminders IS 'User reminders with multi-channel notifications';


--
-- TOC entry 233 (class 1259 OID 16705)
-- Name: pending_reminders; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.pending_reminders AS
 SELECT id,
    message,
    trigger_time,
    notify_voice,
    notify_email,
    notify_sms,
    repeat_type,
    created_at
   FROM public.reminders
  WHERE (((status)::text = 'pending'::text) AND (trigger_time > CURRENT_TIMESTAMP))
  ORDER BY trigger_time;


ALTER VIEW public.pending_reminders OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16569)
-- Name: plc_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plc_tags (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plc_id uuid NOT NULL,
    tag_name character varying(255) NOT NULL,
    tag_type character varying(20) NOT NULL,
    description character varying(255),
    access_type character varying(20) DEFAULT 'read_write'::character varying,
    monitor boolean DEFAULT false,
    monitor_interval integer DEFAULT 1000,
    last_value text,
    last_read timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    read_keywords text,
    write_keywords text,
    on_keywords text,
    off_keywords text
);


ALTER TABLE public.plc_tags OWNER TO postgres;

--
-- TOC entry 5168 (class 0 OID 0)
-- Dependencies: 226
-- Name: TABLE plc_tags; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.plc_tags IS 'PLC tags available for monitoring and control';


--
-- TOC entry 234 (class 1259 OID 16709)
-- Name: plc_tags_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.plc_tags_view AS
 SELECT t.id,
    t.tag_name,
    t.tag_type,
    t.description,
    t.access_type,
    t.monitor,
    t.last_value,
    t.last_read,
    p.name AS plc_name,
    p.ip_address,
    p.plc_type,
    p.connection_status,
    p.enabled AS plc_enabled
   FROM (public.plc_tags t
     JOIN public.plc_config p ON ((t.plc_id = p.id)))
  ORDER BY p.name, t.tag_name;


ALTER VIEW public.plc_tags_view OWNER TO postgres;

--
-- TOC entry 244 (class 1259 OID 16868)
-- Name: program_routines; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.program_routines (
    routine_id integer NOT NULL,
    version_id integer NOT NULL,
    routine_name text NOT NULL,
    routine_type text,
    description text
);


ALTER TABLE public.program_routines OWNER TO postgres;

--
-- TOC entry 243 (class 1259 OID 16867)
-- Name: program_routines_routine_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.program_routines_routine_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.program_routines_routine_id_seq OWNER TO postgres;

--
-- TOC entry 5169 (class 0 OID 0)
-- Dependencies: 243
-- Name: program_routines_routine_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.program_routines_routine_id_seq OWNED BY public.program_routines.routine_id;


--
-- TOC entry 246 (class 1259 OID 16885)
-- Name: program_rungs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.program_rungs (
    rung_id integer NOT NULL,
    routine_id integer NOT NULL,
    rung_number integer NOT NULL,
    rung_text text,
    comment text,
    tags_read text,
    tags_written text
);


ALTER TABLE public.program_rungs OWNER TO postgres;

--
-- TOC entry 245 (class 1259 OID 16884)
-- Name: program_rungs_rung_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.program_rungs_rung_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.program_rungs_rung_id_seq OWNER TO postgres;

--
-- TOC entry 5170 (class 0 OID 0)
-- Dependencies: 245
-- Name: program_rungs_rung_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.program_rungs_rung_id_seq OWNED BY public.program_rungs.rung_id;


--
-- TOC entry 248 (class 1259 OID 16902)
-- Name: program_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.program_tags (
    tag_id integer NOT NULL,
    version_id integer NOT NULL,
    tag_name text NOT NULL,
    tag_type text,
    scope text,
    description text
);


ALTER TABLE public.program_tags OWNER TO postgres;

--
-- TOC entry 247 (class 1259 OID 16901)
-- Name: program_tags_tag_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.program_tags_tag_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.program_tags_tag_id_seq OWNER TO postgres;

--
-- TOC entry 5171 (class 0 OID 0)
-- Dependencies: 247
-- Name: program_tags_tag_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.program_tags_tag_id_seq OWNED BY public.program_tags.tag_id;


--
-- TOC entry 242 (class 1259 OID 16849)
-- Name: program_versions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.program_versions (
    version_id integer NOT NULL,
    plc_id uuid NOT NULL,
    version_name text NOT NULL,
    upload_timestamp timestamp without time zone DEFAULT now(),
    uploaded_by text,
    file_path text,
    checksum text,
    notes text,
    is_active boolean DEFAULT false,
    controller_name text,
    processor_type text,
    major_revision text,
    minor_revision text
);


ALTER TABLE public.program_versions OWNER TO postgres;

--
-- TOC entry 241 (class 1259 OID 16848)
-- Name: program_versions_version_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.program_versions_version_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.program_versions_version_id_seq OWNER TO postgres;

--
-- TOC entry 5172 (class 0 OID 0)
-- Dependencies: 241
-- Name: program_versions_version_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.program_versions_version_id_seq OWNED BY public.program_versions.version_id;


--
-- TOC entry 231 (class 1259 OID 16681)
-- Name: reminder_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reminder_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    reminder_id uuid,
    message text,
    channel character varying(20) NOT NULL,
    result character varying(20) NOT NULL,
    error_message text,
    sent_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.reminder_log OWNER TO postgres;

--
-- TOC entry 5173 (class 0 OID 0)
-- Dependencies: 231
-- Name: TABLE reminder_log; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.reminder_log IS 'History of reminder notifications';


--
-- TOC entry 238 (class 1259 OID 16807)
-- Name: suggestion_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.suggestion_history (
    history_id integer NOT NULL,
    suggestion_id integer NOT NULL,
    action text NOT NULL,
    performed_by text,
    "timestamp" timestamp without time zone DEFAULT now(),
    notes text,
    old_status text,
    new_status text,
    old_value text,
    new_value text
);


ALTER TABLE public.suggestion_history OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16806)
-- Name: suggestion_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.suggestion_history_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.suggestion_history_history_id_seq OWNER TO postgres;

--
-- TOC entry 5174 (class 0 OID 0)
-- Dependencies: 237
-- Name: suggestion_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.suggestion_history_history_id_seq OWNED BY public.suggestion_history.history_id;


--
-- TOC entry 223 (class 1259 OID 16447)
-- Name: system_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.system_logs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    log_level character varying(20),
    message text,
    details jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.system_logs OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 16646)
-- Name: user_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_settings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    setting_key character varying(100) NOT NULL,
    setting_value text,
    setting_type character varying(20) DEFAULT 'string'::character varying,
    description character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_settings OWNER TO postgres;

--
-- TOC entry 5175 (class 0 OID 0)
-- Dependencies: 229
-- Name: TABLE user_settings; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.user_settings IS 'System and user preferences';


--
-- TOC entry 222 (class 1259 OID 16429)
-- Name: web_content; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.web_content (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    url text NOT NULL,
    title character varying(1000),
    content_markdown text,
    content_text text,
    metadata jsonb,
    retrieved_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    conversation_id uuid
);


ALTER TABLE public.web_content OWNER TO postgres;

--
-- TOC entry 4906 (class 2604 OID 16828)
-- Name: agent_pending_suggestions pending_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_pending_suggestions ALTER COLUMN pending_id SET DEFAULT nextval('public.agent_pending_suggestions_pending_id_seq'::regclass);


--
-- TOC entry 4900 (class 2604 OID 16788)
-- Name: optimization_suggestions suggestion_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.optimization_suggestions ALTER COLUMN suggestion_id SET DEFAULT nextval('public.optimization_suggestions_suggestion_id_seq'::regclass);


--
-- TOC entry 4912 (class 2604 OID 16871)
-- Name: program_routines routine_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_routines ALTER COLUMN routine_id SET DEFAULT nextval('public.program_routines_routine_id_seq'::regclass);


--
-- TOC entry 4913 (class 2604 OID 16888)
-- Name: program_rungs rung_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_rungs ALTER COLUMN rung_id SET DEFAULT nextval('public.program_rungs_rung_id_seq'::regclass);


--
-- TOC entry 4914 (class 2604 OID 16905)
-- Name: program_tags tag_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_tags ALTER COLUMN tag_id SET DEFAULT nextval('public.program_tags_tag_id_seq'::regclass);


--
-- TOC entry 4909 (class 2604 OID 16852)
-- Name: program_versions version_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_versions ALTER COLUMN version_id SET DEFAULT nextval('public.program_versions_version_id_seq'::regclass);


--
-- TOC entry 4904 (class 2604 OID 16810)
-- Name: suggestion_history history_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.suggestion_history ALTER COLUMN history_id SET DEFAULT nextval('public.suggestion_history_history_id_seq'::regclass);


--
-- TOC entry 4975 (class 2606 OID 16836)
-- Name: agent_pending_suggestions agent_pending_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_pending_suggestions
    ADD CONSTRAINT agent_pending_suggestions_pkey PRIMARY KEY (pending_id);


--
-- TOC entry 4957 (class 2606 OID 16672)
-- Name: chore_log chore_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chore_log
    ADD CONSTRAINT chore_log_pkey PRIMARY KEY (id);


--
-- TOC entry 4941 (class 2606 OID 16610)
-- Name: chores chores_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chores
    ADD CONSTRAINT chores_pkey PRIMARY KEY (id);


--
-- TOC entry 4916 (class 2606 OID 16411)
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- TOC entry 4921 (class 2606 OID 16423)
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4970 (class 2606 OID 16800)
-- Name: optimization_suggestions optimization_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.optimization_suggestions
    ADD CONSTRAINT optimization_suggestions_pkey PRIMARY KEY (suggestion_id);


--
-- TOC entry 4933 (class 2606 OID 16566)
-- Name: plc_config plc_config_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plc_config
    ADD CONSTRAINT plc_config_pkey PRIMARY KEY (id);


--
-- TOC entry 4937 (class 2606 OID 16584)
-- Name: plc_tags plc_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plc_tags
    ADD CONSTRAINT plc_tags_pkey PRIMARY KEY (id);


--
-- TOC entry 4939 (class 2606 OID 16586)
-- Name: plc_tags plc_tags_plc_id_tag_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plc_tags
    ADD CONSTRAINT plc_tags_plc_id_tag_name_key UNIQUE (plc_id, tag_name);


--
-- TOC entry 4983 (class 2606 OID 16878)
-- Name: program_routines program_routines_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_routines
    ADD CONSTRAINT program_routines_pkey PRIMARY KEY (routine_id);


--
-- TOC entry 4986 (class 2606 OID 16895)
-- Name: program_rungs program_rungs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_rungs
    ADD CONSTRAINT program_rungs_pkey PRIMARY KEY (rung_id);


--
-- TOC entry 4989 (class 2606 OID 16912)
-- Name: program_tags program_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_tags
    ADD CONSTRAINT program_tags_pkey PRIMARY KEY (tag_id);


--
-- TOC entry 4980 (class 2606 OID 16861)
-- Name: program_versions program_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_versions
    ADD CONSTRAINT program_versions_pkey PRIMARY KEY (version_id);


--
-- TOC entry 4964 (class 2606 OID 16692)
-- Name: reminder_log reminder_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reminder_log
    ADD CONSTRAINT reminder_log_pkey PRIMARY KEY (id);


--
-- TOC entry 4950 (class 2606 OID 16642)
-- Name: reminders reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reminders
    ADD CONSTRAINT reminders_pkey PRIMARY KEY (id);


--
-- TOC entry 4973 (class 2606 OID 16818)
-- Name: suggestion_history suggestion_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.suggestion_history
    ADD CONSTRAINT suggestion_history_pkey PRIMARY KEY (history_id);


--
-- TOC entry 4929 (class 2606 OID 16456)
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- TOC entry 4953 (class 2606 OID 16658)
-- Name: user_settings user_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_pkey PRIMARY KEY (id);


--
-- TOC entry 4955 (class 2606 OID 16660)
-- Name: user_settings user_settings_setting_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_setting_key_key UNIQUE (setting_key);


--
-- TOC entry 4924 (class 2606 OID 16439)
-- Name: web_content web_content_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.web_content
    ADD CONSTRAINT web_content_pkey PRIMARY KEY (id);


--
-- TOC entry 4926 (class 2606 OID 16441)
-- Name: web_content web_content_url_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.web_content
    ADD CONSTRAINT web_content_url_key UNIQUE (url);


--
-- TOC entry 4958 (class 1259 OID 16678)
-- Name: idx_chore_log_chore_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chore_log_chore_id ON public.chore_log USING btree (chore_id);


--
-- TOC entry 4959 (class 1259 OID 16679)
-- Name: idx_chore_log_executed_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chore_log_executed_at ON public.chore_log USING btree (executed_at);


--
-- TOC entry 4960 (class 1259 OID 16680)
-- Name: idx_chore_log_result; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chore_log_result ON public.chore_log USING btree (result);


--
-- TOC entry 4942 (class 1259 OID 16621)
-- Name: idx_chores_enabled; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chores_enabled ON public.chores USING btree (enabled);


--
-- TOC entry 4943 (class 1259 OID 16622)
-- Name: idx_chores_next_run; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chores_next_run ON public.chores USING btree (next_run);


--
-- TOC entry 4944 (class 1259 OID 16624)
-- Name: idx_chores_plc_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chores_plc_id ON public.chores USING btree (plc_id);


--
-- TOC entry 4945 (class 1259 OID 16623)
-- Name: idx_chores_schedule_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_chores_schedule_type ON public.chores USING btree (schedule_type);


--
-- TOC entry 4917 (class 1259 OID 16459)
-- Name: idx_conversations_updated; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_conversations_updated ON public.conversations USING btree (updated_at DESC);


--
-- TOC entry 4971 (class 1259 OID 16846)
-- Name: idx_history_suggestion; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_history_suggestion ON public.suggestion_history USING btree (suggestion_id);


--
-- TOC entry 4918 (class 1259 OID 16457)
-- Name: idx_messages_conversation; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_conversation ON public.messages USING btree (conversation_id);


--
-- TOC entry 4919 (class 1259 OID 16458)
-- Name: idx_messages_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_created ON public.messages USING btree (created_at DESC);


--
-- TOC entry 4976 (class 1259 OID 16847)
-- Name: idx_pending_reviewed; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_pending_reviewed ON public.agent_pending_suggestions USING btree (reviewed);


--
-- TOC entry 4930 (class 1259 OID 16568)
-- Name: idx_plc_config_enabled; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_plc_config_enabled ON public.plc_config USING btree (enabled);


--
-- TOC entry 4931 (class 1259 OID 16567)
-- Name: idx_plc_config_ip; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_plc_config_ip ON public.plc_config USING btree (ip_address);


--
-- TOC entry 4934 (class 1259 OID 16593)
-- Name: idx_plc_tags_monitor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_plc_tags_monitor ON public.plc_tags USING btree (monitor);


--
-- TOC entry 4935 (class 1259 OID 16592)
-- Name: idx_plc_tags_plc_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_plc_tags_plc_id ON public.plc_tags USING btree (plc_id);


--
-- TOC entry 4961 (class 1259 OID 16698)
-- Name: idx_reminder_log_reminder_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reminder_log_reminder_id ON public.reminder_log USING btree (reminder_id);


--
-- TOC entry 4962 (class 1259 OID 16699)
-- Name: idx_reminder_log_sent_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reminder_log_sent_at ON public.reminder_log USING btree (sent_at);


--
-- TOC entry 4946 (class 1259 OID 16645)
-- Name: idx_reminders_pending; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reminders_pending ON public.reminders USING btree (status, trigger_time) WHERE ((status)::text = 'pending'::text);


--
-- TOC entry 4947 (class 1259 OID 16643)
-- Name: idx_reminders_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reminders_status ON public.reminders USING btree (status);


--
-- TOC entry 4948 (class 1259 OID 16644)
-- Name: idx_reminders_trigger_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reminders_trigger_time ON public.reminders USING btree (trigger_time);


--
-- TOC entry 4981 (class 1259 OID 16920)
-- Name: idx_routines_version; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_routines_version ON public.program_routines USING btree (version_id);


--
-- TOC entry 4984 (class 1259 OID 16921)
-- Name: idx_rungs_routine; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_rungs_routine ON public.program_rungs USING btree (routine_id);


--
-- TOC entry 4965 (class 1259 OID 16843)
-- Name: idx_suggestions_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggestions_category ON public.optimization_suggestions USING btree (category);


--
-- TOC entry 4966 (class 1259 OID 16845)
-- Name: idx_suggestions_plc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggestions_plc ON public.optimization_suggestions USING btree (plc_id);


--
-- TOC entry 4967 (class 1259 OID 16844)
-- Name: idx_suggestions_priority; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggestions_priority ON public.optimization_suggestions USING btree (priority);


--
-- TOC entry 4968 (class 1259 OID 16842)
-- Name: idx_suggestions_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggestions_status ON public.optimization_suggestions USING btree (status);


--
-- TOC entry 4927 (class 1259 OID 16461)
-- Name: idx_system_logs_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_system_logs_created ON public.system_logs USING btree (created_at DESC);


--
-- TOC entry 4987 (class 1259 OID 16922)
-- Name: idx_tags_version; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tags_version ON public.program_tags USING btree (version_id);


--
-- TOC entry 4951 (class 1259 OID 16661)
-- Name: idx_user_settings_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_settings_key ON public.user_settings USING btree (setting_key);


--
-- TOC entry 4977 (class 1259 OID 16919)
-- Name: idx_versions_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_versions_active ON public.program_versions USING btree (is_active);


--
-- TOC entry 4978 (class 1259 OID 16918)
-- Name: idx_versions_plc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_versions_plc ON public.program_versions USING btree (plc_id);


--
-- TOC entry 4922 (class 1259 OID 16460)
-- Name: idx_web_content_url; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_web_content_url ON public.web_content USING btree (url);


--
-- TOC entry 5004 (class 2620 OID 16469)
-- Name: messages trigger_update_conversation; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_update_conversation AFTER INSERT ON public.messages FOR EACH ROW EXECUTE FUNCTION public.update_conversation_timestamp();


--
-- TOC entry 4999 (class 2606 OID 16837)
-- Name: agent_pending_suggestions agent_pending_suggestions_imported_as_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_pending_suggestions
    ADD CONSTRAINT agent_pending_suggestions_imported_as_suggestion_id_fkey FOREIGN KEY (imported_as_suggestion_id) REFERENCES public.optimization_suggestions(suggestion_id) ON DELETE SET NULL;


--
-- TOC entry 4995 (class 2606 OID 16673)
-- Name: chore_log chore_log_chore_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chore_log
    ADD CONSTRAINT chore_log_chore_id_fkey FOREIGN KEY (chore_id) REFERENCES public.chores(id) ON DELETE SET NULL;


--
-- TOC entry 4993 (class 2606 OID 16611)
-- Name: chores chores_plc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chores
    ADD CONSTRAINT chores_plc_id_fkey FOREIGN KEY (plc_id) REFERENCES public.plc_config(id) ON DELETE SET NULL;


--
-- TOC entry 4994 (class 2606 OID 16616)
-- Name: chores chores_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chores
    ADD CONSTRAINT chores_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.plc_tags(id) ON DELETE SET NULL;


--
-- TOC entry 4990 (class 2606 OID 16424)
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- TOC entry 4997 (class 2606 OID 16801)
-- Name: optimization_suggestions optimization_suggestions_plc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.optimization_suggestions
    ADD CONSTRAINT optimization_suggestions_plc_id_fkey FOREIGN KEY (plc_id) REFERENCES public.plc_config(id) ON DELETE SET NULL;


--
-- TOC entry 4992 (class 2606 OID 16587)
-- Name: plc_tags plc_tags_plc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plc_tags
    ADD CONSTRAINT plc_tags_plc_id_fkey FOREIGN KEY (plc_id) REFERENCES public.plc_config(id) ON DELETE CASCADE;


--
-- TOC entry 5001 (class 2606 OID 16879)
-- Name: program_routines program_routines_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_routines
    ADD CONSTRAINT program_routines_version_id_fkey FOREIGN KEY (version_id) REFERENCES public.program_versions(version_id) ON DELETE CASCADE;


--
-- TOC entry 5002 (class 2606 OID 16896)
-- Name: program_rungs program_rungs_routine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_rungs
    ADD CONSTRAINT program_rungs_routine_id_fkey FOREIGN KEY (routine_id) REFERENCES public.program_routines(routine_id) ON DELETE CASCADE;


--
-- TOC entry 5003 (class 2606 OID 16913)
-- Name: program_tags program_tags_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_tags
    ADD CONSTRAINT program_tags_version_id_fkey FOREIGN KEY (version_id) REFERENCES public.program_versions(version_id) ON DELETE CASCADE;


--
-- TOC entry 5000 (class 2606 OID 16862)
-- Name: program_versions program_versions_plc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.program_versions
    ADD CONSTRAINT program_versions_plc_id_fkey FOREIGN KEY (plc_id) REFERENCES public.plc_config(id) ON DELETE CASCADE;


--
-- TOC entry 4996 (class 2606 OID 16693)
-- Name: reminder_log reminder_log_reminder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reminder_log
    ADD CONSTRAINT reminder_log_reminder_id_fkey FOREIGN KEY (reminder_id) REFERENCES public.reminders(id) ON DELETE SET NULL;


--
-- TOC entry 4998 (class 2606 OID 16819)
-- Name: suggestion_history suggestion_history_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.suggestion_history
    ADD CONSTRAINT suggestion_history_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.optimization_suggestions(suggestion_id) ON DELETE CASCADE;


--
-- TOC entry 4991 (class 2606 OID 16442)
-- Name: web_content web_content_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.web_content
    ADD CONSTRAINT web_content_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


-- Completed on 2026-04-12 10:34:39

--
-- PostgreSQL database dump complete
--

\unrestrict 8a7OchcdNVH4Fc2W5JkWOhzm0hPwyScYFemPyQIBtbzXsVqleeGGT8lvg0r65R5

