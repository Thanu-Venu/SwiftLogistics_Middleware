-- Auto-run once by Postgres on first boot of an empty data volume
-- (docker-entrypoint-initdb.d). Matches the schema the app code expects.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE public.users (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    role text DEFAULT 'client'::text NOT NULL,
    client_id text NOT NULL,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_email_key UNIQUE (email),
    CONSTRAINT users_client_id_key UNIQUE (client_id)
);
CREATE INDEX idx_users_email ON public.users USING btree (email);

CREATE TABLE public.orders (
    id text NOT NULL,
    client_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL,
    created_at bigint NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    last_error text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    assigned_driver_id text,
    last_event_id text,
    CONSTRAINT orders_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_orders_assigned_driver_id ON public.orders USING btree (assigned_driver_id);
CREATE INDEX idx_orders_client_created ON public.orders USING btree (client_id, created_at DESC);
CREATE INDEX idx_orders_client_id ON public.orders USING btree (client_id);
CREATE INDEX idx_orders_status ON public.orders USING btree (status);

CREATE OR REPLACE FUNCTION public.set_updated_at()
  RETURNS trigger
  LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_orders_updated_at
  BEFORE UPDATE ON public.orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.order_events (
    id bigserial NOT NULL,
    order_id text NOT NULL,
    event_type text NOT NULL,
    details jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT order_events_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_order_events_created_at ON public.order_events USING btree (created_at);
CREATE INDEX idx_order_events_order_id ON public.order_events USING btree (order_id, created_at);
CREATE INDEX idx_order_events_type ON public.order_events USING btree (event_type);

CREATE TABLE public.outbox (
    id bigserial NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    published boolean DEFAULT false NOT NULL,
    published_at timestamp with time zone,
    publish_attempts integer DEFAULT 0 NOT NULL,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    CONSTRAINT outbox_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_outbox_aggregate ON public.outbox USING btree (aggregate_type, aggregate_id);
CREATE INDEX idx_outbox_created_at ON public.outbox USING btree (created_at);
CREATE INDEX idx_outbox_unpublished ON public.outbox USING btree (published, created_at);
