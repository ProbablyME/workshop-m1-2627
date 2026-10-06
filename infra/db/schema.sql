CREATE TABLE public.alerts (
    id integer NOT NULL,
    device_id character varying(32) NOT NULL,
    ts timestamp with time zone NOT NULL,
    uptime_ms integer,
    type character varying(32) NOT NULL,
    state character varying(8) NOT NULL,
    value double precision,
    severity character varying(16) NOT NULL,
    source character varying(16) NOT NULL
);
CREATE SEQUENCE public.alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.alerts_id_seq OWNED BY public.alerts.id;
CREATE TABLE public.commands (
    id integer NOT NULL,
    device_id character varying(32) NOT NULL,
    ts timestamp with time zone NOT NULL,
    cmd_id character varying(32) NOT NULL,
    actuator character varying(16) NOT NULL,
    action character varying(16) NOT NULL,
    duration_ms integer,
    published boolean NOT NULL
);
CREATE SEQUENCE public.commands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.commands_id_seq OWNED BY public.commands.id;
CREATE TABLE public.detections (
    id integer NOT NULL,
    ts timestamp with time zone NOT NULL,
    source character varying(32) NOT NULL,
    label character varying(64) NOT NULL,
    confidence double precision NOT NULL,
    bbox json,
    frame_w integer,
    frame_h integer
);
CREATE SEQUENCE public.detections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.detections_id_seq OWNED BY public.detections.id;
CREATE TABLE public.devices (
    id character varying(32) NOT NULL,
    online boolean NOT NULL,
    ip character varying(45),
    fw character varying(16),
    last_seen timestamp with time zone
);
CREATE TABLE public.predictions (
    id integer NOT NULL,
    ts timestamp with time zone NOT NULL,
    model character varying(64) NOT NULL,
    score double precision NOT NULL,
    is_anomaly boolean NOT NULL,
    window_s integer,
    features json
);
CREATE SEQUENCE public.predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.predictions_id_seq OWNED BY public.predictions.id;
CREATE TABLE public.telemetry (
    id integer NOT NULL,
    device_id character varying(32) NOT NULL,
    ts timestamp with time zone NOT NULL,
    uptime_ms integer,
    temperature double precision,
    humidity double precision,
    gas_raw integer,
    gas_ppm double precision,
    motion boolean NOT NULL,
    rssi integer,
    heap_free integer
);
CREATE SEQUENCE public.telemetry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.telemetry_id_seq OWNED BY public.telemetry.id;
ALTER TABLE ONLY public.alerts ALTER COLUMN id SET DEFAULT nextval('public.alerts_id_seq'::regclass);
ALTER TABLE ONLY public.commands ALTER COLUMN id SET DEFAULT nextval('public.commands_id_seq'::regclass);
ALTER TABLE ONLY public.detections ALTER COLUMN id SET DEFAULT nextval('public.detections_id_seq'::regclass);
ALTER TABLE ONLY public.predictions ALTER COLUMN id SET DEFAULT nextval('public.predictions_id_seq'::regclass);
ALTER TABLE ONLY public.telemetry ALTER COLUMN id SET DEFAULT nextval('public.telemetry_id_seq'::regclass);
ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.commands
    ADD CONSTRAINT commands_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.detections
    ADD CONSTRAINT detections_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.predictions
    ADD CONSTRAINT predictions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.telemetry
    ADD CONSTRAINT telemetry_pkey PRIMARY KEY (id);
CREATE INDEX ix_alerts_device_id ON public.alerts USING btree (device_id);
CREATE INDEX ix_alerts_ts ON public.alerts USING btree (ts);
CREATE INDEX ix_commands_device_id ON public.commands USING btree (device_id);
CREATE INDEX ix_detections_ts ON public.detections USING btree (ts);
CREATE INDEX ix_predictions_ts ON public.predictions USING btree (ts);
CREATE INDEX ix_telemetry_device_id ON public.telemetry USING btree (device_id);
CREATE INDEX ix_telemetry_ts ON public.telemetry USING btree (ts);
