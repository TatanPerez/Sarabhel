-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.agents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name character varying NOT NULL,
  role character varying NOT NULL,
  status character varying DEFAULT 'offline'::character varying,
  last_heartbeat timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  last_output text,
  CONSTRAINT agents_pkey PRIMARY KEY (id)
);
CREATE TABLE public.tasks (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  agent_id uuid,
  command text NOT NULL,
  status text DEFAULT 'pending'::text,
  output text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT tasks_pkey PRIMARY KEY (id),
  CONSTRAINT tasks_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id)
);